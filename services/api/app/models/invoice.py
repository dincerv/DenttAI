"""SQLAlchemy models: Invoice and InvoiceItem (clinic-scoped, RLS)."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InvoiceType(str, enum.Enum):
    E_FATURA = "e_fatura"
    E_ARSIV  = "e_arsiv"
    E_SMM    = "e_smm"


class InvoiceStatus(str, enum.Enum):
    DRAFT     = "draft"
    ISSUED    = "issued"
    CANCELLED = "cancelled"


class GibStatus(str, enum.Enum):
    NOT_SENT = "not_sent"
    QUEUED   = "queued"
    SENT     = "sent"
    REJECTED = "rejected"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    patient_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )

    invoice_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False, default=InvoiceType.E_ARSIV.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InvoiceStatus.DRAFT.value)
    gib_status: Mapped[str] = mapped_column(String(20), nullable=False, default=GibStatus.NOT_SENT.value)

    buyer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_tax_id: Mapped[str | None] = mapped_column(String(11), nullable=True)
    buyer_tax_office: Mapped[str | None] = mapped_column(String(100), nullable=True)
    buyer_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("10"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    items: Mapped[list[InvoiceItem]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    clinic_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("10"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="items")
