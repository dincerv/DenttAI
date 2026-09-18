"""Pydantic schemas for clinic-side e-reçete records."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PrescriptionItemCreate(BaseModel):
    drug_name: str = Field(..., min_length=1, max_length=255)
    barcode: str | None = Field(None, max_length=50)
    dosage: str | None = Field(None, max_length=100)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    instructions: str | None = None


class PrescriptionItemResponse(BaseModel):
    id: UUID
    drug_name: str
    barcode: str | None
    dosage: str | None
    quantity: Decimal
    instructions: str | None

    model_config = {"from_attributes": True}


class PrescriptionCreate(BaseModel):
    patient_id: UUID
    appointment_id: UUID | None = None
    diagnosis: str | None = None
    notes: str | None = None
    items: list[PrescriptionItemCreate] = Field(..., min_length=1)


class PrescriptionResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    appointment_id: UUID | None
    doctor_id: UUID | None
    patient_name: str | None = None
    patient_national_id: str | None = None
    doctor_name: str | None = None
    prescription_no: str | None
    status: str
    medula_status: str
    diagnosis: str | None
    notes: str | None
    issued_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    items: list[PrescriptionItemResponse] = []

    model_config = {"from_attributes": True}


class PrescriptionListResponse(BaseModel):
    items: list[PrescriptionResponse]
    total: int


class PrescriptionSummaryResponse(BaseModel):
    draft_count: int
    issued_count: int
    cancelled_count: int
    missing_national_id: int
