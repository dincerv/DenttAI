"""Prescription business logic — clinic-side e-reçete (Medula later)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient import Patient
from app.models.prescription import MedulaStatus, Prescription, PrescriptionItem, PrescriptionStatus
from app.models.user import User
from app.schemas.prescription import (
    PrescriptionCreate,
    PrescriptionItemResponse,
    PrescriptionListResponse,
    PrescriptionResponse,
    PrescriptionSummaryResponse,
)

logger = logging.getLogger(__name__)


def _to_response(
    rx: Prescription,
    patient: Patient | None = None,
    doctor: User | None = None,
) -> PrescriptionResponse:
    return PrescriptionResponse(
        id=rx.id,
        clinic_id=rx.clinic_id,
        patient_id=rx.patient_id,
        appointment_id=rx.appointment_id,
        doctor_id=rx.doctor_id,
        patient_name=patient.full_name if patient else None,
        patient_national_id=patient.national_id if patient else None,
        doctor_name=doctor.full_name if doctor else None,
        prescription_no=rx.prescription_no,
        status=rx.status,
        medula_status=rx.medula_status,
        diagnosis=rx.diagnosis,
        notes=rx.notes,
        issued_at=rx.issued_at,
        cancelled_at=rx.cancelled_at,
        created_at=rx.created_at,
        items=[
            PrescriptionItemResponse(
                id=item.id,
                drug_name=item.drug_name,
                barcode=item.barcode,
                dosage=item.dosage,
                quantity=item.quantity,
                instructions=item.instructions,
            )
            for item in (rx.items or [])
        ],
    )


async def _next_no(db: AsyncSession, clinic_id: UUID) -> str:
    year = datetime.now(timezone.utc).year
    pattern = f"ERC-{year}-%"
    last = (
        await db.execute(
            select(func.max(Prescription.prescription_no)).where(
                Prescription.clinic_id == clinic_id,
                Prescription.prescription_no.like(pattern),
            )
        )
    ).scalar_one()
    seq = 1
    if last and last.rsplit("-", 1)[-1].isdigit():
        seq = int(last.rsplit("-", 1)[-1]) + 1
    return f"ERC-{year}-{seq:05d}"


async def _load(db: AsyncSession, rx_id: UUID) -> tuple[Prescription, Patient | None, User | None]:
    result = await db.execute(
        select(Prescription).where(Prescription.id == rx_id).options(selectinload(Prescription.items))
    )
    rx = result.scalar_one_or_none()
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reçete bulunamadı")
    patient = (
        await db.execute(select(Patient).where(Patient.id == rx.patient_id))
    ).scalar_one_or_none()
    doctor = None
    if rx.doctor_id:
        doctor = (
            await db.execute(select(User).where(User.id == rx.doctor_id))
        ).scalar_one_or_none()
    return rx, patient, doctor


async def list_prescriptions(
    db: AsyncSession,
    clinic_id: UUID,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PrescriptionListResponse:
    filters = [Prescription.clinic_id == clinic_id]
    if status_filter:
        filters.append(Prescription.status == status_filter)

    base = (
        select(Prescription)
        .where(and_(*filters))
        .options(selectinload(Prescription.items))
        .order_by(Prescription.created_at.desc())
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.limit(limit).offset(offset))).scalars().all()

    patient_ids = {r.patient_id for r in rows}
    doctor_ids = {r.doctor_id for r in rows if r.doctor_id}
    patients = {}
    if patient_ids:
        patients = {
            p.id: p
            for p in (await db.execute(select(Patient).where(Patient.id.in_(patient_ids)))).scalars().all()
        }
    doctors = {}
    if doctor_ids:
        doctors = {
            u.id: u
            for u in (await db.execute(select(User).where(User.id.in_(doctor_ids)))).scalars().all()
        }
    return PrescriptionListResponse(
        items=[_to_response(r, patients.get(r.patient_id), doctors.get(r.doctor_id) if r.doctor_id else None) for r in rows],
        total=total,
    )


async def get_prescription(db: AsyncSession, rx_id: UUID) -> PrescriptionResponse:
    rx, patient, doctor = await _load(db, rx_id)
    return _to_response(rx, patient, doctor)


async def get_summary(db: AsyncSession, clinic_id: UUID) -> PrescriptionSummaryResponse:
    q = select(
        func.count().filter(Prescription.status == PrescriptionStatus.DRAFT.value).label("draft_count"),
        func.count().filter(Prescription.status == PrescriptionStatus.ISSUED.value).label("issued_count"),
        func.count().filter(Prescription.status == PrescriptionStatus.CANCELLED.value).label("cancelled_count"),
    ).where(Prescription.clinic_id == clinic_id)
    row = (await db.execute(q)).one()

    missing = (
        await db.execute(
            select(func.count())
            .select_from(Prescription)
            .join(Patient, Patient.id == Prescription.patient_id)
            .where(
                Prescription.clinic_id == clinic_id,
                Prescription.status != PrescriptionStatus.CANCELLED.value,
                (Patient.national_id.is_(None) | (Patient.national_id == "")),
            )
        )
    ).scalar_one()

    return PrescriptionSummaryResponse(
        draft_count=row.draft_count,
        issued_count=row.issued_count,
        cancelled_count=row.cancelled_count,
        missing_national_id=missing,
    )


async def create_prescription(
    db: AsyncSession,
    clinic_id: UUID,
    data: PrescriptionCreate,
    created_by: UUID,
    role: str,
) -> PrescriptionResponse:
    patient = (
        await db.execute(
            select(Patient).where(Patient.id == data.patient_id, Patient.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hasta bulunamadı")

    rx = Prescription(
        clinic_id=clinic_id,
        patient_id=patient.id,
        appointment_id=data.appointment_id,
        doctor_id=created_by,
        status=PrescriptionStatus.DRAFT.value,
        medula_status=MedulaStatus.NOT_SENT.value,
        diagnosis=data.diagnosis,
        notes=data.notes,
        created_by=created_by,
    )
    db.add(rx)
    await db.flush()

    for item in data.items:
        db.add(PrescriptionItem(
            prescription_id=rx.id,
            clinic_id=clinic_id,
            drug_name=item.drug_name.strip(),
            barcode=item.barcode,
            dosage=item.dosage,
            quantity=item.quantity or Decimal("1"),
            instructions=item.instructions,
        ))
    await db.flush()
    loaded, _, doctor = await _load(db, rx.id)
    logger.info("Reçete taslağı oluşturuldu: %s klinik=%s", rx.id, clinic_id)
    return _to_response(loaded, patient, doctor)


async def issue_prescription(db: AsyncSession, clinic_id: UUID, rx_id: UUID) -> PrescriptionResponse:
    rx, patient, doctor = await _load(db, rx_id)
    if rx.status != PrescriptionStatus.DRAFT.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sadece taslak reçete kesilebilir")
    if not rx.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="İlaç kalemi olmayan reçete kesilemez")
    rx.prescription_no = await _next_no(db, clinic_id)
    rx.status = PrescriptionStatus.ISSUED.value
    rx.issued_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Reçete kesildi: %s no=%s", rx.id, rx.prescription_no)
    loaded, patient, doctor = await _load(db, rx.id)
    return _to_response(loaded, patient, doctor)


async def cancel_prescription(db: AsyncSession, rx_id: UUID) -> PrescriptionResponse:
    rx, patient, doctor = await _load(db, rx_id)
    if rx.status == PrescriptionStatus.CANCELLED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reçete zaten iptal")
    rx.status = PrescriptionStatus.CANCELLED.value
    rx.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Reçete iptal edildi: %s", rx.id)
    loaded, patient, doctor = await _load(db, rx.id)
    return _to_response(loaded, patient, doctor)
