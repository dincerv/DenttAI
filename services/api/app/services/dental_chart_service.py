"""Diş şeması ve tedavi planı iş mantığı."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dental import ProcedureType, ToothRecord, ToothStatus, Treatment, TreatmentStatus
from app.models.patient import Patient
from app.schemas.dental import (
    ChartResponse,
    FDI_PERMANENT,
    ToothState,
    ToothUpsert,
    TreatmentComplete,
    TreatmentCreate,
    TreatmentListResponse,
    TreatmentResponse,
    TreatmentUpdate,
)
from app.models.payment import PayerType
from app.schemas.payment import PaymentCreate
from app.services.payment_service import create_payment

PROCEDURE_TOOTH_STATUS: dict[str, str] = {
    ProcedureType.DOLGU.value: ToothStatus.FILLED.value,
    ProcedureType.KANAL.value: ToothStatus.RCT.value,
    ProcedureType.KRON.value: ToothStatus.CROWN.value,
    ProcedureType.VENEER.value: ToothStatus.CROWN.value,
    ProcedureType.CEKIM.value: ToothStatus.MISSING.value,
    ProcedureType.IMPLANT.value: ToothStatus.IMPLANT.value,
    ProcedureType.KOPRU.value: ToothStatus.BRIDGE.value,
}


async def _patient(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> Patient:
    row = (
        await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hasta bulunamadi")
    return row


def _treatment_response(row: Treatment) -> TreatmentResponse:
    return TreatmentResponse.model_validate(row)


async def get_chart(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> ChartResponse:
    await _patient(db, clinic_id, patient_id)
    rows = (
        await db.execute(
            select(ToothRecord).where(
                ToothRecord.clinic_id == clinic_id,
                ToothRecord.patient_id == patient_id,
            )
        )
    ).scalars().all()
    by_tooth = {r.tooth_fdi: r for r in rows}
    teeth = [
        ToothState(
            tooth_fdi=n,
            status=by_tooth[n].status if n in by_tooth else ToothStatus.HEALTHY.value,
            notes=by_tooth[n].notes if n in by_tooth else None,
        )
        for n in sorted(FDI_PERMANENT)
    ]
    return ChartResponse(patient_id=patient_id, teeth=teeth)


async def upsert_tooth(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
    tooth_fdi: int,
    body: ToothUpsert,
    user_id: UUID,
) -> ToothState:
    if tooth_fdi not in FDI_PERMANENT:
        raise HTTPException(status_code=400, detail="Gecersiz dis numarasi")
    await _patient(db, clinic_id, patient_id)
    row = (
        await db.execute(
            select(ToothRecord).where(
                ToothRecord.clinic_id == clinic_id,
                ToothRecord.patient_id == patient_id,
                ToothRecord.tooth_fdi == tooth_fdi,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ToothRecord(
            clinic_id=clinic_id,
            patient_id=patient_id,
            tooth_fdi=tooth_fdi,
            status=body.status.value,
            notes=body.notes,
            updated_by=user_id,
        )
        db.add(row)
    else:
        row.status = body.status.value
        row.notes = body.notes
        row.updated_by = user_id
    await db.flush()
    return ToothState(tooth_fdi=row.tooth_fdi, status=row.status, notes=row.notes)


async def list_treatments(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
) -> TreatmentListResponse:
    await _patient(db, clinic_id, patient_id)
    rows = (
        await db.execute(
            select(Treatment)
            .where(Treatment.clinic_id == clinic_id, Treatment.patient_id == patient_id)
            .order_by(Treatment.created_at.desc())
        )
    ).scalars().all()
    planned = sum((r.price for r in rows if r.status == TreatmentStatus.PLANNED.value), Decimal("0"))
    done = sum((r.price for r in rows if r.status == TreatmentStatus.COMPLETED.value), Decimal("0"))
    return TreatmentListResponse(
        items=[_treatment_response(r) for r in rows],
        total=len(rows),
        planned_total=planned,
        completed_total=done,
    )


async def create_treatment(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
    body: TreatmentCreate,
    user_id: UUID,
    role: str,
) -> TreatmentResponse:
    await _patient(db, clinic_id, patient_id)
    row = Treatment(
        clinic_id=clinic_id,
        patient_id=patient_id,
        tooth_fdi=body.tooth_fdi,
        procedure=body.procedure.value,
        status=TreatmentStatus.PLANNED.value,
        price=body.price,
        notes=body.notes,
        appointment_id=body.appointment_id,
        doctor_id=user_id if role == "doctor" else None,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    if body.tooth_fdi:
        await upsert_tooth(
            db, clinic_id, patient_id, body.tooth_fdi,
            ToothUpsert(status=ToothStatus.PLANNED, notes=None),
            user_id,
        )
    return _treatment_response(row)


async def update_treatment(
    db: AsyncSession,
    clinic_id: UUID,
    treatment_id: UUID,
    body: TreatmentUpdate,
) -> TreatmentResponse:
    row = (
        await db.execute(
            select(Treatment).where(Treatment.id == treatment_id, Treatment.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tedavi bulunamadi")
    if row.status != TreatmentStatus.PLANNED.value:
        raise HTTPException(status_code=400, detail="Sadece planli tedavi guncellenir")
    payload = body.model_dump(exclude_unset=True)
    if "procedure" in payload and body.procedure is not None:
        row.procedure = body.procedure.value
    if "tooth_fdi" in payload:
        row.tooth_fdi = body.tooth_fdi
    if "price" in payload and body.price is not None:
        row.price = body.price
    if "notes" in payload:
        row.notes = body.notes
    if "appointment_id" in payload:
        row.appointment_id = body.appointment_id
    await db.flush()
    return _treatment_response(row)


async def complete_treatment(
    db: AsyncSession,
    clinic_id: UUID,
    treatment_id: UUID,
    body: TreatmentComplete,
    user_id: UUID,
) -> TreatmentResponse:
    row = (
        await db.execute(
            select(Treatment).where(Treatment.id == treatment_id, Treatment.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tedavi bulunamadi")
    if row.status != TreatmentStatus.PLANNED.value:
        raise HTTPException(status_code=400, detail="Sadece planli tedavi tamamlanir")

    row.status = TreatmentStatus.COMPLETED.value
    row.completed_at = datetime.now(timezone.utc)
    if row.doctor_id is None:
        row.doctor_id = user_id

    mapped = PROCEDURE_TOOTH_STATUS.get(row.procedure)
    if mapped and row.tooth_fdi:
        await upsert_tooth(
            db, clinic_id, row.patient_id, row.tooth_fdi,
            ToothUpsert(status=ToothStatus(mapped), notes=None),
            user_id,
        )

    if body.create_charge and row.price and row.price > 0 and row.payment_id is None:
        payment = await create_payment(
            db,
            clinic_id,
            PaymentCreate(
                patient_id=row.patient_id,
                amount=row.price,
                description=f"{row.procedure} diş {row.tooth_fdi}" if row.tooth_fdi else row.procedure,
                treatment_type=row.procedure,
                payer_type=PayerType.PATIENT,
            ),
            user_id,
        )
        row.payment_id = payment.id

    await db.flush()
    return _treatment_response(row)


async def cancel_treatment(
    db: AsyncSession,
    clinic_id: UUID,
    treatment_id: UUID,
) -> TreatmentResponse:
    row = (
        await db.execute(
            select(Treatment).where(Treatment.id == treatment_id, Treatment.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tedavi bulunamadi")
    if row.status == TreatmentStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Tamamlanan tedavi iptal edilemez")
    row.status = TreatmentStatus.CANCELLED.value
    await db.flush()
    return _treatment_response(row)
