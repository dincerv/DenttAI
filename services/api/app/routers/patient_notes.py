"""
Patient Notes Router — /patient-notes
Hasta notları: tedavi kayıtları (doktor), AI geri bildirimleri (WhatsApp), genel notlar.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from shared.auth_middleware import get_verified_claims, set_rls_context

from pydantic import BaseModel, Field
from datetime import datetime, timedelta

router = APIRouter(prefix="/patient-notes", tags=["Patient Notes"])


def _add_date_filters(
    conditions: list[str],
    params: dict,
    date_from: str | None,
    date_to: str | None,
) -> None:
    """date_from / date_to → datetime nesnelerine çevirip filtre ekler (asyncpg uyumlu)."""
    if date_from:
        conditions.append("pn.created_at >= :dfrom")
        params["dfrom"] = datetime.fromisoformat(date_from)
    if date_to:
        conditions.append("pn.created_at < :dto")
        params["dto"] = datetime.fromisoformat(date_to) + timedelta(days=1)


# ── Schemas ───────────────────────────────────────────────
class PatientNoteCreate(BaseModel):
    patient_id: UUID
    appointment_id: UUID | None = None
    note_type: str = Field(default="treatment", description="treatment | ai_feedback | general")
    content: str = Field(..., min_length=1, max_length=5000)


class PatientNoteResponse(BaseModel):
    id: str
    clinic_id: str
    patient_id: str
    doctor_id: str | None
    doctor_name: str | None = None
    patient_name: str | None = None
    appointment_id: str | None
    note_type: str
    content: str
    created_at: str


class PatientNotesSummary(BaseModel):
    """Doktor/admin dashboard: günlük/haftalık/aylık/yıllık tedavi log özeti."""
    doctor_id: str
    doctor_name: str
    specialty: str | None = None
    period: str
    treatment_count: int
    notes: list[PatientNoteResponse]


# ── CREATE ────────────────────────────────────────────────
@router.post(
    "",
    response_model=PatientNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Hasta notu ekle (tedavi kaydı, AI geri bildirim, genel not)",
)
async def create_note(
    data: PatientNoteCreate,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> PatientNoteResponse:
    await set_rls_context(db, claims["clinic_id"])

    # Doktor rolünde ise doctor_id'yi bul
    doctor_id = None
    if data.note_type != "ai_feedback" and claims.get("role") in ("doctor", "owner"):
        row = (await db.execute(
            text("SELECT id FROM doctors WHERE user_id = :uid AND clinic_id = :cid LIMIT 1"),
            {"uid": str(claims["user_id"]), "cid": str(claims["clinic_id"])},
        )).mappings().first()
        if row:
            doctor_id = str(row["id"])

    result = (await db.execute(
        text("""
            INSERT INTO patient_notes (clinic_id, patient_id, doctor_id, appointment_id, note_type, content)
            VALUES (:cid, :pid, :did, :aid, :ntype, :content)
            RETURNING id, clinic_id, patient_id, doctor_id, appointment_id, note_type, content, created_at
        """),
        {
            "cid": str(claims["clinic_id"]),
            "pid": str(data.patient_id),
            "did": doctor_id,
            "aid": str(data.appointment_id) if data.appointment_id else None,
            "ntype": data.note_type,
            "content": data.content,
        },
    )).mappings().first()
    await db.commit()

    return PatientNoteResponse(
        id=str(result["id"]),
        clinic_id=str(result["clinic_id"]),
        patient_id=str(result["patient_id"]),
        doctor_id=str(result["doctor_id"]) if result["doctor_id"] else None,
        appointment_id=str(result["appointment_id"]) if result["appointment_id"] else None,
        note_type=result["note_type"],
        content=result["content"],
        created_at=result["created_at"].isoformat(),
    )


# ── LIST (patient-specific) ──────────────────────────────
@router.get(
    "",
    response_model=list[PatientNoteResponse],
    summary="Hasta notlarını listele (filtre: patient_id, doctor_id, note_type, tarih)",
)
async def list_notes(
    patient_id: str | None = Query(default=None),
    doctor_id: str | None = Query(default=None),
    note_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD"),
    limit: int = Query(default=100, ge=1, le=500),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> list[PatientNoteResponse]:
    await set_rls_context(db, claims["clinic_id"])

    conditions = ["pn.clinic_id = :cid"]
    params: dict = {"cid": str(claims["clinic_id"]), "lim": limit}

    if patient_id:
        conditions.append("pn.patient_id = :pid")
        params["pid"] = patient_id
    if doctor_id:
        conditions.append("pn.doctor_id = :did")
        params["did"] = doctor_id
    if note_type:
        conditions.append("pn.note_type = :ntype")
        params["ntype"] = note_type
    _add_date_filters(conditions, params, date_from, date_to)

    where = " AND ".join(conditions)

    rows = (await db.execute(
        text(f"""
            SELECT pn.id, pn.clinic_id, pn.patient_id, pn.doctor_id,
                   pn.appointment_id, pn.note_type, pn.content, pn.created_at,
                   d.full_name AS doctor_name,
                   p.full_name AS patient_name
            FROM patient_notes pn
            LEFT JOIN doctors d ON d.id = pn.doctor_id
            LEFT JOIN patients p ON p.id = pn.patient_id
            WHERE {where}
            ORDER BY pn.created_at DESC
            LIMIT :lim
        """),
        params,
    )).mappings().all()

    return [
        PatientNoteResponse(
            id=str(r["id"]),
            clinic_id=str(r["clinic_id"]),
            patient_id=str(r["patient_id"]),
            doctor_id=str(r["doctor_id"]) if r["doctor_id"] else None,
            doctor_name=r.get("doctor_name"),
            patient_name=r.get("patient_name"),
            appointment_id=str(r["appointment_id"]) if r["appointment_id"] else None,
            note_type=r["note_type"],
            content=r["content"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


# ── DOCTOR TREATMENT LOG (for dashboard) ──────────────────
@router.get(
    "/my-log",
    response_model=list[PatientNoteResponse],
    summary="Doktorun kendi tedavi notları (dashboard için)",
)
async def my_treatment_log(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> list[PatientNoteResponse]:
    await set_rls_context(db, claims["clinic_id"])

    # Find doctor_id for current user
    doc_row = (await db.execute(
        text("SELECT id FROM doctors WHERE user_id = :uid AND clinic_id = :cid LIMIT 1"),
        {"uid": str(claims["user_id"]), "cid": str(claims["clinic_id"])},
    )).mappings().first()

    if not doc_row:
        return []

    conditions = ["pn.clinic_id = :cid", "pn.doctor_id = :did"]
    params: dict = {"cid": str(claims["clinic_id"]), "did": str(doc_row["id"]), "lim": limit}

    _add_date_filters(conditions, params, date_from, date_to)

    where = " AND ".join(conditions)

    rows = (await db.execute(
        text(f"""
            SELECT pn.id, pn.clinic_id, pn.patient_id, pn.doctor_id,
                   pn.appointment_id, pn.note_type, pn.content, pn.created_at,
                   d.full_name AS doctor_name,
                   p.full_name AS patient_name
            FROM patient_notes pn
            LEFT JOIN doctors d ON d.id = pn.doctor_id
            LEFT JOIN patients p ON p.id = pn.patient_id
            WHERE {where}
            ORDER BY pn.created_at DESC
            LIMIT :lim
        """),
        params,
    )).mappings().all()

    return [
        PatientNoteResponse(
            id=str(r["id"]),
            clinic_id=str(r["clinic_id"]),
            patient_id=str(r["patient_id"]),
            doctor_id=str(r["doctor_id"]) if r["doctor_id"] else None,
            doctor_name=r.get("doctor_name"),
            patient_name=r.get("patient_name"),
            appointment_id=str(r["appointment_id"]) if r["appointment_id"] else None,
            note_type=r["note_type"],
            content=r["content"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


# ── ALL DOCTORS LOG (for admin/owner dashboard) ────────────
@router.get(
    "/all-log",
    response_model=list[PatientNotesSummary],
    summary="Tüm doktorların tedavi logları (admin/owner dashboard)",
)
async def all_doctors_log(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    group_by: str = Query(default="day", description="day | week | month | year"),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> list[PatientNotesSummary]:
    await set_rls_context(db, claims["clinic_id"])

    # period truncation
    trunc_map = {"day": "day", "week": "week", "month": "month", "year": "year"}
    trunc = trunc_map.get(group_by, "day")

    conditions = ["pn.clinic_id = :cid", "pn.note_type = 'treatment'"]
    params: dict = {"cid": str(claims["clinic_id"])}

    _add_date_filters(conditions, params, date_from, date_to)

    where = " AND ".join(conditions)

    # Get summary: count per doctor per period
    summary_rows = (await db.execute(
        text(f"""
            SELECT
                pn.doctor_id,
                d.full_name AS doctor_name,
                d.specialty,
                date_trunc('{trunc}', pn.created_at) AS period,
                COUNT(*) AS treatment_count
            FROM patient_notes pn
            LEFT JOIN doctors d ON d.id = pn.doctor_id
            WHERE {where}
            GROUP BY pn.doctor_id, d.full_name, d.specialty, date_trunc('{trunc}', pn.created_at)
            ORDER BY period DESC, d.full_name
        """),
        params,
    )).mappings().all()

    # Get actual notes for each group
    note_rows = (await db.execute(
        text(f"""
            SELECT pn.id, pn.clinic_id, pn.patient_id, pn.doctor_id,
                   pn.appointment_id, pn.note_type, pn.content, pn.created_at,
                   d.full_name AS doctor_name,
                   p.full_name AS patient_name
            FROM patient_notes pn
            LEFT JOIN doctors d ON d.id = pn.doctor_id
            LEFT JOIN patients p ON p.id = pn.patient_id
            WHERE {where}
            ORDER BY pn.created_at DESC
            LIMIT 500
        """),
        params,
    )).mappings().all()

    # Group notes by (doctor_id, period)
    from collections import defaultdict
    grouped_notes: dict[tuple, list[PatientNoteResponse]] = defaultdict(list)
    for r in note_rows:
        period_key = r["created_at"].strftime(
            "%Y-%m-%d" if trunc == "day" else
            "%Y-W%W" if trunc == "week" else
            "%Y-%m" if trunc == "month" else "%Y"
        )
        key = (str(r["doctor_id"]) if r["doctor_id"] else "none", period_key)
        grouped_notes[key].append(PatientNoteResponse(
            id=str(r["id"]),
            clinic_id=str(r["clinic_id"]),
            patient_id=str(r["patient_id"]),
            doctor_id=str(r["doctor_id"]) if r["doctor_id"] else None,
            doctor_name=r.get("doctor_name"),
            patient_name=r.get("patient_name"),
            appointment_id=str(r["appointment_id"]) if r["appointment_id"] else None,
            note_type=r["note_type"],
            content=r["content"],
            created_at=r["created_at"].isoformat(),
        ))

    results = []
    for sr in summary_rows:
        period_str = sr["period"].strftime(
            "%Y-%m-%d" if trunc == "day" else
            "%Y-W%W" if trunc == "week" else
            "%Y-%m" if trunc == "month" else "%Y"
        )
        key = (str(sr["doctor_id"]) if sr["doctor_id"] else "none", period_str)
        results.append(PatientNotesSummary(
            doctor_id=str(sr["doctor_id"]) if sr["doctor_id"] else "unknown",
            doctor_name=sr["doctor_name"] or "Bilinmeyen",
            specialty=sr.get("specialty"),
            period=period_str,
            treatment_count=sr["treatment_count"],
            notes=grouped_notes.get(key, []),
        ))

    return results
