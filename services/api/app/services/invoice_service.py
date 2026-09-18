"""Invoice business logic — clinic-side e-Fatura / e-Arşiv records."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, InvoiceType, GibStatus
from app.models.patient import Patient
from app.models.payment import Payment
from app.schemas.invoice import (
    EligiblePayment,
    EligiblePaymentsResponse,
    InvoiceCreate,
    InvoiceFromPayment,
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceSummaryResponse,
)

logger = logging.getLogger(__name__)

TWOPLACES = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _split_vat(total: Decimal, vat_rate: Decimal) -> tuple[Decimal, Decimal]:
    if vat_rate <= 0:
        return _money(total), Decimal("0.00")
    subtotal = _money(total / (1 + vat_rate / Decimal("100")))
    return subtotal, _money(total - subtotal)


def _infer_type(tax_id: str | None, explicit: str | None) -> str:
    if explicit in (
        InvoiceType.E_FATURA.value,
        InvoiceType.E_ARSIV.value,
        InvoiceType.E_SMM.value,
    ):
        return explicit
    digits = "".join(c for c in (tax_id or "") if c.isdigit())
    if len(digits) == 10:
        return InvoiceType.E_FATURA.value
    return InvoiceType.E_ARSIV.value


def _to_response(inv: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=inv.id,
        clinic_id=inv.clinic_id,
        patient_id=inv.patient_id,
        payment_id=inv.payment_id,
        invoice_no=inv.invoice_no,
        invoice_type=inv.invoice_type,
        status=inv.status,
        gib_status=inv.gib_status,
        buyer_name=inv.buyer_name,
        buyer_tax_id=inv.buyer_tax_id,
        buyer_tax_office=inv.buyer_tax_office,
        buyer_address=inv.buyer_address,
        subtotal=inv.subtotal,
        vat_rate=inv.vat_rate,
        vat_amount=inv.vat_amount,
        total=inv.total,
        description=inv.description,
        notes=inv.notes,
        issued_at=inv.issued_at,
        cancelled_at=inv.cancelled_at,
        created_at=inv.created_at,
        items=[
            InvoiceItemResponse(
                id=item.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                vat_rate=item.vat_rate,
                line_total=item.line_total,
            )
            for item in (inv.items or [])
        ],
    )


async def _next_invoice_no(db: AsyncSession, clinic_id: UUID, invoice_type: str) -> str:
    year = datetime.now(timezone.utc).year
    prefix = {
        InvoiceType.E_FATURA.value: "EFA",
        InvoiceType.E_SMM.value: "ESM",
    }.get(invoice_type, "EAR")
    pattern = f"{prefix}-{year}-%"
    last = (
        await db.execute(
            select(func.max(Invoice.invoice_no)).where(
                Invoice.clinic_id == clinic_id,
                Invoice.invoice_no.like(pattern),
            )
        )
    ).scalar_one()
    seq = 1
    if last and last.rsplit("-", 1)[-1].isdigit():
        seq = int(last.rsplit("-", 1)[-1]) + 1
    return f"{prefix}-{year}-{seq:05d}"


async def _load(db: AsyncSession, invoice_id: UUID) -> Invoice:
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.items))
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadı")
    return invoice


async def list_invoices(
    db: AsyncSession,
    clinic_id: UUID,
    status_filter: str | None = None,
    invoice_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> InvoiceListResponse:
    filters = [Invoice.clinic_id == clinic_id]
    if status_filter:
        filters.append(Invoice.status == status_filter)
    if invoice_type:
        filters.append(Invoice.invoice_type == invoice_type)

    base = (
        select(Invoice)
        .where(and_(*filters))
        .options(selectinload(Invoice.items))
        .order_by(Invoice.created_at.desc())
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.limit(limit).offset(offset))).scalars().all()
    return InvoiceListResponse(items=[_to_response(r) for r in rows], total=total)


async def get_invoice(db: AsyncSession, invoice_id: UUID) -> InvoiceResponse:
    return _to_response(await _load(db, invoice_id))


async def get_summary(db: AsyncSession, clinic_id: UUID) -> InvoiceSummaryResponse:
    q = select(
        func.count().filter(Invoice.status == InvoiceStatus.DRAFT.value).label("draft_count"),
        func.count().filter(Invoice.status == InvoiceStatus.ISSUED.value).label("issued_count"),
        func.count().filter(Invoice.status == InvoiceStatus.CANCELLED.value).label("cancelled_count"),
        func.coalesce(
            func.sum(Invoice.total).filter(Invoice.status == InvoiceStatus.ISSUED.value), 0
        ).label("issued_total"),
        func.count().filter(
            and_(Invoice.invoice_type == InvoiceType.E_ARSIV.value, Invoice.status != InvoiceStatus.CANCELLED.value)
        ).label("e_arsiv_count"),
        func.count().filter(
            and_(Invoice.invoice_type == InvoiceType.E_FATURA.value, Invoice.status != InvoiceStatus.CANCELLED.value)
        ).label("e_fatura_count"),
        func.count().filter(
            and_(Invoice.invoice_type == InvoiceType.E_SMM.value, Invoice.status != InvoiceStatus.CANCELLED.value)
        ).label("e_smm_count"),
    ).where(Invoice.clinic_id == clinic_id)
    row = (await db.execute(q)).one()
    return InvoiceSummaryResponse(
        draft_count=row.draft_count,
        issued_count=row.issued_count,
        cancelled_count=row.cancelled_count,
        issued_total=Decimal(str(row.issued_total)),
        e_arsiv_count=row.e_arsiv_count,
        e_fatura_count=row.e_fatura_count,
        e_smm_count=row.e_smm_count,
    )


async def list_eligible_payments(db: AsyncSession, clinic_id: UUID) -> EligiblePaymentsResponse:
    invoiced = select(Invoice.payment_id).where(
        Invoice.clinic_id == clinic_id,
        Invoice.payment_id.is_not(None),
        Invoice.status != InvoiceStatus.CANCELLED.value,
    )
    rows = (
        await db.execute(
            select(Payment)
            .where(
                Payment.clinic_id == clinic_id,
                Payment.status != "cancelled",
                ~Payment.id.in_(invoiced),
            )
            .order_by(Payment.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return EligiblePaymentsResponse(
        items=[
            EligiblePayment(
                id=p.id,
                patient_id=p.patient_id,
                patient_name=p.patient_name,
                amount=p.amount,
                treatment_type=p.treatment_type,
                status=p.status,
            )
            for p in rows
        ]
    )


async def create_invoice(
    db: AsyncSession,
    clinic_id: UUID,
    data: InvoiceCreate,
    created_by: UUID,
) -> InvoiceResponse:
    patient = (
        await db.execute(
            select(Patient).where(Patient.id == data.patient_id, Patient.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hasta bulunamadı")

    if data.payment_id:
        await _assert_payment_free(db, clinic_id, data.payment_id)

    tax_id = data.buyer_tax_id or patient.national_id
    invoice_type = _infer_type(tax_id, data.invoice_type)
    vat_rate = data.vat_rate
    subtotal, vat_amount = _split_vat(data.total, vat_rate)

    invoice = Invoice(
        clinic_id=clinic_id,
        patient_id=patient.id,
        payment_id=data.payment_id,
        invoice_type=invoice_type,
        status=InvoiceStatus.DRAFT.value,
        gib_status=GibStatus.NOT_SENT.value,
        buyer_name=(data.buyer_name or patient.full_name).strip(),
        buyer_tax_id=tax_id,
        buyer_tax_office=data.buyer_tax_office,
        buyer_address=data.buyer_address,
        subtotal=subtotal,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total=_money(data.total),
        description=data.description,
        notes=data.notes,
        created_by=created_by,
    )
    db.add(invoice)
    await db.flush()

    items = data.items or [
        InvoiceItemCreate(
            description=data.description or "Diş tedavisi",
            quantity=Decimal("1"),
            unit_price=subtotal,
        )
    ]
    for item in items:
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            clinic_id=clinic_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=_money(item.unit_price),
            vat_rate=vat_rate,
            line_total=_money(item.quantity * item.unit_price),
        ))
    await db.flush()
    loaded = await _load(db, invoice.id)
    logger.info("Fatura taslağı oluşturuldu: %s klinik=%s", invoice.id, clinic_id)
    return _to_response(loaded)


async def create_from_payment(
    db: AsyncSession,
    clinic_id: UUID,
    payment_id: UUID,
    data: InvoiceFromPayment,
    created_by: UUID,
) -> InvoiceResponse:
    payment = (
        await db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.clinic_id == clinic_id)
        )
    ).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ödeme bulunamadı")
    if payment.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="İptal ödemeden fatura kesilemez")

    patient = (
        await db.execute(select(Patient).where(Patient.id == payment.patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hasta bulunamadı")

    body = InvoiceCreate(
        patient_id=patient.id,
        payment_id=payment.id,
        invoice_type=data.invoice_type,
        buyer_name=patient.full_name,
        buyer_tax_id=patient.national_id,
        vat_rate=data.vat_rate,
        total=payment.amount,
        description=payment.treatment_type or payment.description or "Diş tedavisi",
        notes=data.notes,
        items=[],
    )
    return await create_invoice(db, clinic_id, body, created_by)


async def _assert_payment_free(db: AsyncSession, clinic_id: UUID, payment_id: UUID) -> None:
    existing = (
        await db.execute(
            select(Invoice.id).where(
                Invoice.clinic_id == clinic_id,
                Invoice.payment_id == payment_id,
                Invoice.status != InvoiceStatus.CANCELLED.value,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu ödeme için zaten fatura var",
        )


async def issue_invoice(db: AsyncSession, clinic_id: UUID, invoice_id: UUID) -> InvoiceResponse:
    invoice = await _load(db, invoice_id)
    if invoice.status != InvoiceStatus.DRAFT.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sadece taslak fatura kesilebilir")
    invoice.invoice_no = await _next_invoice_no(db, clinic_id, invoice.invoice_type)
    invoice.status = InvoiceStatus.ISSUED.value
    invoice.issued_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Fatura kesildi: %s no=%s", invoice.id, invoice.invoice_no)
    return _to_response(await _load(db, invoice.id))


async def cancel_invoice(db: AsyncSession, invoice_id: UUID) -> InvoiceResponse:
    invoice = await _load(db, invoice_id)
    if invoice.status == InvoiceStatus.CANCELLED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fatura zaten iptal")
    invoice.status = InvoiceStatus.CANCELLED.value
    invoice.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("Fatura iptal edildi: %s", invoice.id)
    return _to_response(await _load(db, invoice.id))
