"""
Pydantic schemas: Payment request/response modelleri.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.payment import PaymentMethod, PaymentStatus, PayerType


# ── Transaction schemas ───────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Ödenen tutar (TL)")
    payment_method: str = Field(..., description="Ödeme yöntemi")
    notes: str | None = None


class TransactionResponse(BaseModel):
    id: UUID
    payment_id: UUID
    amount: Decimal
    payment_method: str
    notes: str | None
    created_at: datetime
    created_by: UUID | None

    model_config = {"from_attributes": True}


# ── Payment schemas ───────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    patient_id: UUID | None = None
    patient_name: str | None = None
    patient_phone: str | None = None
    national_id: str | None = Field(None, min_length=11, max_length=11)
    appointment_id: UUID | None = None

    amount: Decimal = Field(..., gt=0, description="Total charge (TL)")
    description: str | None = Field(None, max_length=500)
    treatment_type: str | None = Field(None, max_length=100)
    payment_method: PaymentMethod | None = None

    payer_type: PayerType | None = None
    insurance_amount: Decimal | None = Field(None, ge=0)
    insurance_type: str | None = Field(None, pattern="^(none|sgk|private|mixed)$")
    insurance_provider: str | None = Field(None, max_length=100)
    insurance_number: str | None = Field(None, max_length=50)

    installment_count: int = Field(default=1, ge=1, le=60)
    due_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_patient_identity(self) -> "PaymentCreate":
        if self.patient_id is None and not (self.patient_name or "").strip():
            raise ValueError("patient_id or patient_name is required")
        if self.insurance_amount is not None and self.insurance_amount > self.amount:
            raise ValueError("insurance_amount cannot exceed amount")
        return self


class PaymentUpdate(BaseModel):
    description: str | None = None
    treatment_type: str | None = None
    due_date: date | None = None
    notes: str | None = None
    status: PaymentStatus | None = None


class PaymentResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    patient_name: str | None
    appointment_id: UUID | None

    amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal

    status: PaymentStatus
    description: str | None
    treatment_type: str | None
    payment_method: PaymentMethod | None

    payer_type: str = "patient"
    insurance_amount: Decimal = Decimal("0")
    patient_amount: Decimal = Decimal("0")

    installment_count: int
    due_date: date | None
    paid_at: datetime | None
    notes: str | None

    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    transactions: list[TransactionResponse] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_remaining(self) -> "PaymentResponse":
        self.remaining_amount = self.amount - self.paid_amount
        return self


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int


class PaymentSummaryResponse(BaseModel):
    """Klinik geneli ödeme özeti — dashboard widget için."""
    total_receivable: Decimal    # toplam borçlu tutar
    total_paid: Decimal          # toplam tahsil edilen
    total_remaining: Decimal     # tahsil edilemeyen
    overdue_count: int           # vadesi geçmiş ödeme sayısı
    overdue_amount: Decimal      # vadesi geçmiş toplam tutar
    pending_count: int
    partial_count: int
    paid_count: int
    sgk_remaining: Decimal = Decimal("0")
    private_remaining: Decimal = Decimal("0")
