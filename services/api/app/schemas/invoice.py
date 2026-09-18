"""Pydantic schemas for invoices."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class InvoiceItemCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(..., ge=0)


class InvoiceItemResponse(BaseModel):
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    patient_id: UUID
    payment_id: UUID | None = None
    invoice_type: str | None = Field(None, pattern="^(e_fatura|e_arsiv|e_smm)$")
    buyer_name: str | None = Field(None, max_length=255)
    buyer_tax_id: str | None = Field(None, max_length=11)
    buyer_tax_office: str | None = Field(None, max_length=100)
    buyer_address: str | None = None
    vat_rate: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    total: Decimal = Field(..., gt=0)
    description: str | None = None
    notes: str | None = None
    items: list[InvoiceItemCreate] = []


class InvoiceFromPayment(BaseModel):
    vat_rate: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    invoice_type: str | None = Field(None, pattern="^(e_fatura|e_arsiv|e_smm)$")
    notes: str | None = None


class InvoiceResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    payment_id: UUID | None
    invoice_no: str | None
    invoice_type: str
    status: str
    gib_status: str
    buyer_name: str
    buyer_tax_id: str | None
    buyer_tax_office: str | None
    buyer_address: str | None
    subtotal: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total: Decimal
    description: str | None
    notes: str | None
    issued_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    items: list[InvoiceItemResponse] = []

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int


class InvoiceSummaryResponse(BaseModel):
    draft_count: int
    issued_count: int
    cancelled_count: int
    issued_total: Decimal
    e_arsiv_count: int
    e_fatura_count: int
    e_smm_count: int = 0


class EligiblePayment(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str | None
    amount: Decimal
    treatment_type: str | None
    status: str


class EligiblePaymentsResponse(BaseModel):
    items: list[EligiblePayment]
