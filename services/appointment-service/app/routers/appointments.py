"""
Appointment Router — /appointments
Multi-tenancy: her endpoint'te RLS context set edilir.
"""
from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.appointment import AppointmentStatus
from app.schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdateRequest,
)
from app.services.appointment_service import (
    create_appointment,
    delete_appointment,
    get_appointment,
    list_appointments,
    update_appointment,
)
from shared.auth_middleware import (
    get_verified_claims,
    require_page_permission,
    require_role,
    set_rls_context,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni randevu oluştur",
    dependencies=[Depends(require_page_permission("appointments_write"))],
)
async def create(
    data: AppointmentCreateRequest,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    await set_rls_context(db, claims["clinic_id"])
    return await create_appointment(data, claims["clinic_id"], db)


@router.get(
    "",
    response_model=AppointmentListResponse,
    summary="Randevuları listele (filtre: branş, durum, tarih, doktor)",
)
async def list_all(
    specialty: str | None = Query(default=None, description="Branş filtresi"),
    appt_status: AppointmentStatus | None = Query(default=None, alias="status"),
    date_from: str | None = Query(default=None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="Bitiş tarihi (YYYY-MM-DD)"),
    doctor_id: str | None = Query(default=None, description="Doktor UUID filtresi"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> AppointmentListResponse:
    await set_rls_context(db, claims["clinic_id"])
    return await list_appointments(
        claims["clinic_id"], db, specialty, appt_status, skip, limit,
        date_from=date_from, date_to=date_to, doctor_id=doctor_id,
    )


# ── Doctors list (for calendar filter) ────────────────────────────────────

from pydantic import BaseModel as _BaseModel

class DoctorSummary(_BaseModel):
    id: str
    full_name: str
    specialty: str | None = None

class DoctorsListResponse(_BaseModel):
    doctors: list[DoctorSummary]


class PatientSummary(_BaseModel):
    id: str
    full_name: str
    phone: str | None = None


class PatientsListResponse(_BaseModel):
    patients: list[PatientSummary]


class PatientCreateRequest(_BaseModel):
    full_name: str
    phone: str
    email: str | None = None


class PatientUpdateRequest(_BaseModel):
    full_name: str | None = None
    phone: str | None = None


def _normalize_tr_phone_to_e164(phone: str) -> str:
    raw = (phone or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Hasta telefonu zorunludur")

    digits = re.sub(r"\D", "", raw)
    if digits.startswith("90") and len(digits) == 12:
        local = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        local = digits[1:]
    elif len(digits) == 10:
        local = digits
    else:
        raise HTTPException(status_code=400, detail="Telefon +90 ile gecerli formatta olmali")

    if len(local) != 10:
        raise HTTPException(status_code=400, detail="Telefon +90 ile gecerli formatta olmali")

    return f"+90{local}"

@router.get(
    "/doctors",
    response_model=DoctorsListResponse,
    summary="Kliniğe ait doktorları listele",
)
async def list_doctors(
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> DoctorsListResponse:
    await set_rls_context(db, claims["clinic_id"])
    rows = (await db.execute(
        text("""
            SELECT d.id, d.full_name, d.specialty
            FROM doctors d
            LEFT JOIN users u ON u.id = d.user_id
            WHERE d.clinic_id = :cid
              AND (
                    -- Hesabı olmayan / demo doktorlar (user_id NULL)
                    d.user_id IS NULL
                 OR (u.is_active = true AND u.role = 'doctor')
                 OR EXISTS (
                        SELECT 1 FROM appointments a
                        WHERE a.clinic_id = d.clinic_id
                          AND a.doctor_id = d.id
                    )
              )
            ORDER BY CASE WHEN u.id IS NULL THEN 1 ELSE 0 END, d.full_name
        """),
        {"cid": str(claims["clinic_id"])},
    )).mappings().all()
    return DoctorsListResponse(
        doctors=[DoctorSummary(id=str(r["id"]), full_name=r["full_name"], specialty=r.get("specialty")) for r in rows]
    )


@router.get(
    "/patients",
    response_model=PatientsListResponse,
    summary="Kliniğe ait hastaları listele (manuel randevu için)",
)
async def list_patients(
    q: str | None = Query(default=None, description="Hasta adı/telefon arama"),
    limit: int = Query(default=30, ge=1, le=200),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> PatientsListResponse:
    await set_rls_context(db, claims["clinic_id"])
    q_clean = q.strip() if q else None
    pattern = f"%{q_clean}%" if q_clean else None
    q_fold = (
        q_clean.lower()
        .replace("ç", "c")
        .replace("ğ", "g")
        .replace("ı", "i")
        .replace("ö", "o")
        .replace("ş", "s")
        .replace("ü", "u")
        if q_clean
        else None
    )
    pattern_fold = f"%{q_fold}%" if q_fold else None
    query_text = """
        SELECT p.id, p.full_name, p.phone
        FROM patients p
        WHERE p.clinic_id = :cid
          AND (
                :q IS NULL
                OR p.full_name ILIKE :pattern
                OR translate(lower(p.full_name), 'çğıöşü', 'cgiosu') ILIKE :pattern_fold
                OR COALESCE(p.phone, '') ILIKE :pattern
          )
        ORDER BY p.full_name
        LIMIT :limit
    """
    pattern = f"%{q.strip()}%" if q and q.strip() else None
    rows = (await db.execute(
        text(query_text),
        {
            "cid": str(claims["clinic_id"]),
            "q": q_clean,
            "pattern": pattern,
            "pattern_fold": pattern_fold,
            "limit": limit,
        },
    )).mappings().all()
    return PatientsListResponse(
        patients=[
            PatientSummary(
                id=str(r["id"]),
                full_name=r["full_name"],
                phone=r.get("phone"),
            )
            for r in rows
        ]
    )


@router.post(
    "/patients",
    response_model=PatientSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Manuel randevu icin yeni hasta olustur",
    dependencies=[Depends(require_page_permission("appointments_write"))],
)
async def create_patient(
    data: PatientCreateRequest,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> PatientSummary:
    await set_rls_context(db, claims["clinic_id"])

    full_name = data.full_name.strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="Hasta adi zorunludur")

    phone = _normalize_tr_phone_to_e164(data.phone)

    email = data.email.strip() if data.email else None

    try:
        row = (
            await db.execute(
                text(
                    """
                    INSERT INTO patients (clinic_id, full_name, phone, email)
                    VALUES (:cid, :full_name, :phone, :email)
                    RETURNING id, full_name, phone
                    """
                ),
                {
                    "cid": str(claims["clinic_id"]),
                    "full_name": full_name,
                    "phone": phone,
                    "email": email,
                },
            )
        ).mappings().first()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        row = (
            await db.execute(
                text(
                    """
                    SELECT id, full_name, phone
                    FROM patients
                    WHERE clinic_id = :cid
                      AND LOWER(TRIM(full_name)) = LOWER(TRIM(:full_name))
                      AND COALESCE(phone, '') = COALESCE(:phone, '')
                    LIMIT 1
                    """
                ),
                {
                    "cid": str(claims["clinic_id"]),
                    "full_name": full_name,
                    "phone": phone,
                },
            )
        ).mappings().first()
        if row is None:
            raise

    return PatientSummary(id=str(row["id"]), full_name=row["full_name"], phone=row.get("phone"))


@router.patch(
    "/patients/{patient_id}",
    response_model=PatientSummary,
    summary="Hasta bilgisi guncelle (ad/telefon)",
    dependencies=[Depends(require_page_permission("appointments_write"))],
)
async def update_patient(
    patient_id: UUID,
    data: PatientUpdateRequest,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> PatientSummary:
    await set_rls_context(db, claims["clinic_id"])

    if data.full_name is None and data.phone is None:
        raise HTTPException(status_code=400, detail="En az bir alan guncellenmeli")

    full_name = data.full_name.strip() if data.full_name is not None else None
    phone = _normalize_tr_phone_to_e164(data.phone) if data.phone is not None else None

    row = (
        await db.execute(
            text(
                """
                UPDATE patients
                SET
                    full_name = COALESCE(:full_name, full_name),
                    phone = COALESCE(:phone, phone)
                WHERE id = :pid AND clinic_id = :cid
                RETURNING id, full_name, phone
                """
            ),
            {
                "full_name": full_name if full_name else None,
                "phone": phone,
                "pid": str(patient_id),
                "cid": str(claims["clinic_id"]),
            },
        )
    ).mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="Hasta bulunamadi")

    await db.commit()
    return PatientSummary(id=str(row["id"]), full_name=row["full_name"], phone=row.get("phone"))


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Randevu detayı getir",
)
async def get_one(
    appointment_id: UUID,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    await set_rls_context(db, claims["clinic_id"])
    return await get_appointment(appointment_id, claims["clinic_id"], db)


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Randevu güncelle — iptal edilirse WaitlistEngine otomatik tetiklenir",
    dependencies=[Depends(require_page_permission("appointments_write"))],
)
async def update(
    appointment_id: UUID,
    data: AppointmentUpdateRequest,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    await set_rls_context(db, claims["clinic_id"])
    return await update_appointment(appointment_id, claims["clinic_id"], data, db)


@router.delete(
    "/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Randevuyu sil (yalnızca owner veya doctor)",
    dependencies=[Depends(require_role("owner", "doctor"))],
    response_class=Response,
)
async def delete(
    appointment_id: UUID,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await set_rls_context(db, claims["clinic_id"])
    await delete_appointment(appointment_id, claims["clinic_id"], db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Patient notes ─────────────────────────────────────────

class _PatientNotesRequest(_BaseModel):
    notes: str | None = None

@router.patch(
    "/patients/{patient_id}/notes",
    summary="Hasta notlarını güncelle (kalıcı — patients tablosunda)",
)
async def update_patient_notes(
    patient_id: UUID,
    data: _PatientNotesRequest,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    await db.execute(
        text("UPDATE patients SET notes = :notes WHERE id = :pid AND clinic_id = :cid"),
        {"notes": data.notes, "pid": str(patient_id), "cid": str(claims["clinic_id"])},
    )
    await db.commit()
    return {"ok": True}
