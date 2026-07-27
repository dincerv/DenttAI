"""
Pydantic schemas: Waitlist request/response modelleri.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────────────────

class WaitlistAddRequest(BaseModel):
    patient_id: UUID
    specialty: str = Field(..., description="Branş: Ortodonti, Pedodonti, vb.")
    doctor_id: UUID | None = Field(default=None, description="Hangi doktorun randevusundan geldi")
    priority: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Öncelik skoru — düşük sayı = yüksek öncelik",
    )
    preferred_days: str | None = Field(
        default=None,
        description="Tercih edilen günler (örn: 'Pazartesi,Çarşamba')",
    )
    notes: str | None = None


class WaitlistUpdateRequest(BaseModel):
    priority: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None
    preferred_days: str | None = None
    notes: str | None = None


# ── Response Schemas ──────────────────────────────────────

class WaitlistResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    doctor_id: UUID | None = None
    specialty: str
    priority: int
    is_active: bool
    preferred_days: str | None
    notes: str | None
    created_at: datetime
    # Enriched via JOIN
    patient_name: str | None = None
    doctor_name: str | None = None
    patient_notes: str | None = None
    next_appointment_date: str | None = None


class WaitlistMatchResponse(BaseModel):
    """
    Yedek listeden eşleşme bulunduğunda döner.
    Hem iptal bilgisini hem de eşleşen yedek hastayı içerir.
    """
    cancelled_appointment_id: UUID
    matched_waitlist_entry_id: UUID
    patient_id: UUID
    specialty: str
    priority: int
    event_published: bool
