"""
Payment Service — ödeme iş mantığı.
Router'lar buraya delege eder; DB işlemleri burada yapılır.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.patient import Patient, InsuranceType
from app.models.payment import Payment, PaymentStatus, PaymentTransaction, PayerType
from app.schemas.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentSummaryResponse,
    PaymentUpdate,
    TransactionCreate,
    TransactionResponse,
)

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _payment_to_response(p: Payment) -> PaymentResponse:
    remaining = p.amount - p.paid_amount
    return PaymentResponse(
        id=p.id,
        clinic_id=p.clinic_id,
        patient_id=p.patient_id,
        patient_name=p.patient_name,
        appointment_id=p.appointment_id,
        amount=p.amount,
        paid_amount=p.paid_amount,
        remaining_amount=remaining,
        status=p.status,
        description=p.description,
        treatment_type=p.treatment_type,
        payment_method=p.payment_method,
        payer_type=getattr(p, "payer_type", "patient") or "patient",
        insurance_amount=getattr(p, "insurance_amount", Decimal("0")) or Decimal("0"),
        patient_amount=getattr(p, "patient_amount", p.amount) or Decimal("0"),
        installment_count=p.installment_count,
        due_date=p.due_date,
        paid_at=p.paid_at,
        notes=p.notes,
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
        transactions=[
            TransactionResponse(
                id=t.id,
                payment_id=t.payment_id,
                amount=t.amount,
                payment_method=t.payment_method,
                notes=t.notes,
                created_at=t.created_at,
                created_by=t.created_by,
            )
            for t in (p.transactions or [])
        ],
    )


def _recalculate_status(payment: Payment) -> None:
    """paid_amount'a göre status'u günceller."""
    if payment.paid_amount <= 0:
        payment.status = PaymentStatus.PENDING
    elif payment.paid_amount >= payment.amount:
        payment.status = PaymentStatus.PAID
        if payment.paid_at is None:
            payment.paid_at = datetime.now(timezone.utc)
    else:
        payment.status = PaymentStatus.PARTIAL


def _split_payer_amounts(
    amount: Decimal,
    payer_type: str,
    insurance_amount: Decimal | None,
) -> tuple[Decimal, Decimal]:
    if payer_type in (PayerType.SGK.value, PayerType.PRIVATE.value):
        covered = insurance_amount if insurance_amount is not None else amount
        return covered, amount - covered
    if payer_type == PayerType.MIXED.value:
        covered = insurance_amount or Decimal("0")
        return covered, amount - covered
    return Decimal("0"), amount


def _payer_from_insurance(insurance_type: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit
    if insurance_type == InsuranceType.SGK.value:
        return PayerType.SGK.value
    if insurance_type == InsuranceType.PRIVATE.value:
        return PayerType.PRIVATE.value
    if insurance_type == InsuranceType.MIXED.value:
        return PayerType.MIXED.value
    return PayerType.PATIENT.value


async def _resolve_patient(
    db: AsyncSession,
    clinic_id: UUID,
    data: PaymentCreate,
) -> Patient:
    if data.patient_id:
        result = await db.execute(
            select(Patient).where(Patient.id == data.patient_id, Patient.clinic_id == clinic_id)
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hasta bulunamadı")
        if data.insurance_type:
            patient.insurance_type = data.insurance_type
        if data.insurance_provider:
            patient.insurance_provider = data.insurance_provider
        if data.insurance_number:
            patient.insurance_number = data.insurance_number
        if data.national_id:
            patient.national_id = data.national_id
        return patient

    full_name = (data.patient_name or "").strip()
    phone = (data.patient_phone or "").strip() or None
    national_id = (data.national_id or "").strip() or None

    if national_id:
        existing = (
            await db.execute(
                select(Patient).where(
                    Patient.clinic_id == clinic_id,
                    Patient.national_id == national_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing

    existing_by_name = (
        await db.execute(
            select(Patient).where(
                Patient.clinic_id == clinic_id,
                func.lower(func.trim(Patient.full_name)) == full_name.lower(),
                func.coalesce(Patient.phone, "") == (phone or ""),
            )
        )
    ).scalar_one_or_none()
    if existing_by_name:
        if data.insurance_type:
            existing_by_name.insurance_type = data.insurance_type
        if national_id and not existing_by_name.national_id:
            existing_by_name.national_id = national_id
        return existing_by_name

    patient = Patient(
        clinic_id=clinic_id,
        full_name=full_name,
        phone=phone,
        national_id=national_id,
        insurance_type=data.insurance_type or InsuranceType.NONE.value,
        insurance_provider=data.insurance_provider,
        insurance_number=data.insurance_number,
    )
    db.add(patient)
    await db.flush()
    return patient

async def list_payments(
    db: AsyncSession,
    clinic_id: UUID,
    status_filter: str | None = None,
    patient_id: UUID | None = None,
    overdue_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> PaymentListResponse:
    filters = []
    if status_filter:
        filters.append(Payment.status == status_filter)
    if patient_id:
        filters.append(Payment.patient_id == patient_id)
    if overdue_only:
        today = date.today()
        filters.append(Payment.due_date < today)
        filters.append(Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL]))

    base_q = (
        select(Payment)
        .where(and_(*filters) if filters else True)
        .options(selectinload(Payment.transactions))
        .order_by(Payment.created_at.desc())
    )

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    result = await db.execute(base_q.limit(limit).offset(offset))
    payments = result.scalars().all()

    return PaymentListResponse(
        items=[_payment_to_response(p) for p in payments],
        total=total,
    )


async def get_payment(db: AsyncSession, payment_id: UUID) -> PaymentResponse:
    result = await db.execute(
        select(Payment)
        .where(Payment.id == payment_id)
        .options(selectinload(Payment.transactions))
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ödeme bulunamadı")
    return _payment_to_response(payment)


async def create_payment(
    db: AsyncSession,
    clinic_id: UUID,
    data: PaymentCreate,
    created_by: UUID,
) -> PaymentResponse:
    patient = await _resolve_patient(db, clinic_id, data)
    payer_type = _payer_from_insurance(
        data.insurance_type or patient.insurance_type,
        data.payer_type.value if data.payer_type else None,
    )
    insurance_amount, patient_amount = _split_payer_amounts(
        data.amount, payer_type, data.insurance_amount,
    )

    payment = Payment(
        clinic_id=clinic_id,
        patient_id=patient.id,
        patient_name=patient.full_name,
        appointment_id=data.appointment_id,
        amount=data.amount,
        paid_amount=Decimal("0"),
        status=PaymentStatus.PENDING.value,
        description=data.description,
        treatment_type=data.treatment_type,
        payment_method=data.payment_method.value if data.payment_method else None,
        payer_type=payer_type,
        insurance_amount=insurance_amount,
        patient_amount=patient_amount,
        installment_count=data.installment_count,
        due_date=data.due_date,
        notes=data.notes,
        created_by=created_by,
    )
    db.add(payment)
    await db.flush()
    # Refresh + transactions eager load
    result = await db.execute(
        select(Payment)
        .where(Payment.id == payment.id)
        .options(selectinload(Payment.transactions))
    )
    payment = result.scalar_one()
    logger.info("Ödeme oluşturuldu: %s (klinik=%s, tutar=%s)", payment.id, clinic_id, data.amount)
    return _payment_to_response(payment)


async def update_payment(
    db: AsyncSession,
    payment_id: UUID,
    data: PaymentUpdate,
) -> PaymentResponse:
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id).options(selectinload(Payment.transactions))
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ödeme bulunamadı")

    if payment.status in (PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="İptal veya iade edilmiş ödeme güncellenemez",
        )

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(payment, field, value)

    return _payment_to_response(payment)


async def cancel_payment(db: AsyncSession, payment_id: UUID) -> PaymentResponse:
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id).options(selectinload(Payment.transactions))
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ödeme bulunamadı")
    if payment.status == PaymentStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tahsil edilmiş ödeme iptal edilemez. İade işlemi için durumu 'refunded' yapın.",
        )
    payment.status = PaymentStatus.CANCELLED
    return _payment_to_response(payment)


# ── Transaction ────────────────────────────────────────────────────────────

async def add_transaction(
    db: AsyncSession,
    payment_id: UUID,
    clinic_id: UUID,
    data: TransactionCreate,
    created_by: UUID,
) -> PaymentResponse:
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id).options(selectinload(Payment.transactions))
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ödeme bulunamadı")

    if payment.status in (PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="İptal/iade edilmiş ödemeye işlem eklenemez",
        )

    remaining = payment.amount - payment.paid_amount
    if data.amount > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ödeme tutarı ({data.amount} TL) kalan borçtan ({remaining} TL) fazla olamaz",
        )

    tx = PaymentTransaction(
        payment_id=payment_id,
        clinic_id=clinic_id,
        amount=data.amount,
        payment_method=data.payment_method,
        notes=data.notes,
        created_by=created_by,
    )
    db.add(tx)
    payment.paid_amount += data.amount
    _recalculate_status(payment)
    await db.flush()
    # Re-fetch with updated transactions
    result2 = await db.execute(
        select(Payment)
        .where(Payment.id == payment_id)
        .options(selectinload(Payment.transactions))
    )
    payment = result2.scalar_one()
    logger.info(
        "Ödeme işlemi eklendi: payment=%s, tutar=%s, yeni_paid=%s",
        payment_id, data.amount, payment.paid_amount,
    )
    return _payment_to_response(payment)


# ── Summary ────────────────────────────────────────────────────────────────

async def get_summary(db: AsyncSession, clinic_id: UUID) -> PaymentSummaryResponse:
    today = date.today()

    # Tüm aktif ödemelerin toplam tutarları
    q = select(
        func.coalesce(func.sum(Payment.amount), 0).label("total_amount"),
        func.coalesce(func.sum(Payment.paid_amount), 0).label("total_paid"),
        func.count().filter(Payment.status == PaymentStatus.PENDING).label("pending_count"),
        func.count().filter(Payment.status == PaymentStatus.PARTIAL).label("partial_count"),
        func.count().filter(Payment.status == PaymentStatus.PAID).label("paid_count"),
    ).where(Payment.status.not_in([PaymentStatus.CANCELLED, PaymentStatus.REFUNDED]))

    row = (await db.execute(q)).one()

    # Vadesi geçmiş
    overdue_q = select(
        func.count().label("count"),
        func.coalesce(func.sum(Payment.amount - Payment.paid_amount), 0).label("amount"),
    ).where(
        and_(
            Payment.due_date < today,
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL]),
        )
    )
    overdue_row = (await db.execute(overdue_q)).one()

    insurance_q = select(
        func.coalesce(
            func.sum(Payment.amount - Payment.paid_amount).filter(Payment.payer_type == PayerType.SGK.value),
            0,
        ).label("sgk_remaining"),
        func.coalesce(
            func.sum(Payment.amount - Payment.paid_amount).filter(Payment.payer_type == PayerType.PRIVATE.value),
            0,
        ).label("private_remaining"),
    ).where(Payment.status.in_([PaymentStatus.PENDING.value, PaymentStatus.PARTIAL.value]))
    insurance_row = (await db.execute(insurance_q)).one()

    total_amount = Decimal(str(row.total_amount))
    total_paid = Decimal(str(row.total_paid))

    return PaymentSummaryResponse(
        total_receivable=total_amount,
        total_paid=total_paid,
        total_remaining=total_amount - total_paid,
        overdue_count=overdue_row.count,
        overdue_amount=Decimal(str(overdue_row.amount)),
        pending_count=row.pending_count,
        partial_count=row.partial_count,
        paid_count=row.paid_count,
        sgk_remaining=Decimal(str(insurance_row.sgk_remaining)),
        private_remaining=Decimal(str(insurance_row.private_remaining)),
    )
