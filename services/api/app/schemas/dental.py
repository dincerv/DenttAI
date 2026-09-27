"""Pydantic şemaları — diş şeması ve tedavi planı."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.dental import ProcedureType, ToothStatus, TreatmentStatus

FDI_PERMANENT = frozenset(
    n for q in (10, 20, 30, 40) for n in range(q + 1, q + 9)
)


def _check_fdi(v: int | None) -> int | None:
    if v is None:
        return None
    if v not in FDI_PERMANENT:
        raise ValueError("Dis numarasi FDI (11-18, 21-28, 31-38, 41-48) olmali")
    return v


class ToothState(BaseModel):
    tooth_fdi: int
    status: str
    notes: str | None = None

    @field_validator("tooth_fdi")
    @classmethod
    def fdi(cls, v: int) -> int:
        checked = _check_fdi(v)
        assert checked is not None
        return checked


class ChartResponse(BaseModel):
    patient_id: UUID
    teeth: list[ToothState]


class ToothUpsert(BaseModel):
    status: ToothStatus
    notes: str | None = Field(None, max_length=500)


class TreatmentCreate(BaseModel):
    tooth_fdi: int | None = None
    procedure: ProcedureType
    price: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = Field(None, max_length=1000)
    appointment_id: UUID | None = None

    @field_validator("tooth_fdi")
    @classmethod
    def fdi(cls, v: int | None) -> int | None:
        return _check_fdi(v)


class TreatmentUpdate(BaseModel):
    procedure: ProcedureType | None = None
    tooth_fdi: int | None = None
    price: Decimal | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=1000)
    appointment_id: UUID | None = None

    @field_validator("tooth_fdi")
    @classmethod
    def fdi(cls, v: int | None) -> int | None:
        return _check_fdi(v)


class TreatmentComplete(BaseModel):
    create_charge: bool = True


class TreatmentResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    tooth_fdi: int | None
    procedure: str
    status: str
    price: Decimal
    notes: str | None
    appointment_id: UUID | None
    payment_id: UUID | None
    doctor_id: UUID | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TreatmentListResponse(BaseModel):
    items: list[TreatmentResponse]
    total: int
    planned_total: Decimal = Decimal("0")
    completed_total: Decimal = Decimal("0")
