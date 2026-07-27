"""Pydantic şemaları: Döngü (cycle) yönetimi — başlatma, bitirme, listeleme."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CycleEndRequest(BaseModel):
    qr_id: str = Field(..., description="Döngüsü kapatılacak QR ID")
    end_reason: str | None = Field(None, max_length=255)
    waste_note: str | None = Field(None)


class CycleEndResponse(BaseModel):
    material_id: UUID
    qr_id: str
    name: str
    start_date: date | None
    end_date: date | None
    expected_lifespan: int | None
    actual_lifespan: int | None
    is_high_waste: bool
    end_reason: str | None
    waste_note: str | None
    anomaly_message: str | None = None

    model_config = {"from_attributes": True}


class CycleMaterialResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    qr_id: str
    shelf_code: str | None
    name: str
    category: str | None
    start_date: date | None
    end_date: date | None
    activated_at: datetime | None = None
    expected_lifespan: int | None
    actual_lifespan: int | None
    is_active: bool
    is_high_waste: bool
    end_reason: str | None
    waste_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
