"""
Pydantic schemas: Appointment request/response modelleri.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.appointment import AppointmentStatus

# ── Request Schemas ──────────────────────────────────────

VALID_SPECIALTIES = {
    "Ortodonti",
    "Pedodonti",
    "İmplant",
    "Cerrahi",
    "Endodonti",
    "Periodontoloji",
    "Protez",
    "Genel Diş Hekimliği",
}


class AppointmentCreateRequest(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    specialty: str = Field(..., description="Branş: Ortodonti, Pedodonti, vb.")
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=240, description="Dakika cinsinden randevu süresi (15-240)")
    is_new_patient: bool = Field(default=False, description="Randevu bazında hasta tipi: True=yeni, False=eski")
    treatment_follow_up_enabled: bool = Field(default=False, description="Tedavi kontrolü: True=açık (mesaj gönder), False=kapalı")
    type: str | None = None
    notes: str | None = None

    @field_validator("specialty")
    @classmethod
    def validate_specialty(cls, v: str) -> str:
        if v not in VALID_SPECIALTIES:
            raise ValueError(
                f"Geçersiz branş: {v}. Geçerli değerler: {sorted(VALID_SPECIALTIES)}"
            )
        return v


class AppointmentUpdateRequest(BaseModel):
    status: AppointmentStatus | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=15, le=240, description="Dakika cinsinden randevu süresi (15-240)")
    is_new_patient: bool | None = None
    treatment_follow_up_enabled: bool | None = None
    notes: str | None = None
    type: str | None = None
    doctor_id: UUID | None = None
    specialty: str | None = None

    @field_validator("specialty")
    @classmethod
    def validate_specialty_update(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in VALID_SPECIALTIES:
            raise ValueError(
                f"Geçersiz branş: {v}. Geçerli değerler: {sorted(VALID_SPECIALTIES)}"
            )
        return v


# ── Response Schemas ────────────────────────────────────────

class AppointmentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    doctor_id: UUID
    specialty: str | None = None
    scheduled_at: datetime
    duration_minutes: int
    treatment_follow_up_enabled: bool
    is_new_patient: bool
    status: AppointmentStatus
    type: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None = None
    # Enriched via JOIN
    doctor_name: str | None = None
    patient_name: str | None = None
    patient_phone: str | None = None


class AppointmentListResponse(BaseModel):
    items: list[AppointmentResponse]
    total: int
