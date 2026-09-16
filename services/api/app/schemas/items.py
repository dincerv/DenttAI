"""Pydantic şemaları: Envanter kalemleri (InventoryItem) — Batch/Parti destekli."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ItemBase(BaseModel):
    name: str = Field(..., max_length=255)
    category: str | None = Field(None, max_length=100)
    quantity: float = Field(..., ge=0)
    unit: str = Field(..., max_length=50)
    min_stock_level: float = Field(0.0, ge=0)
    cost_per_unit: float | None = Field(None, ge=0)
    shelf_code: str | None = Field(None, max_length=20)
    expiry_date: date | None = Field(None)
    batch_number: str | None = Field(None, max_length=100, description="Parti/lot numarası")


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    category: str | None = Field(None, max_length=100)
    quantity: float | None = Field(None, ge=0)
    unit: str | None = Field(None, max_length=50)
    min_stock_level: float | None = Field(None, ge=0)
    cost_per_unit: float | None = Field(None, ge=0)
    shelf_code: str | None = Field(None, max_length=20)
    expiry_date: date | None = Field(None)
    batch_number: str | None = Field(None, max_length=100)


class AdjustQuantityRequest(BaseModel):
    delta: float = Field(..., description="Pozitif = stok ekle, Negatif = stok düş")
    reason: str | None = Field(None, max_length=255)

    @field_validator("delta")
    @classmethod
    def delta_nonzero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("delta sıfır olamaz")
        return v


class AdjustmentResponse(BaseModel):
    id: UUID
    item_id: UUID
    delta: float
    reason: str | None
    performed_by_email: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ItemResponse(ItemBase):
    id: UUID
    clinic_id: UUID
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime | None
    shelf_code: str | None = None
    expiry_date: date | None = None
    batch_number: str | None = None

    model_config = {"from_attributes": True}


# ── Batch (Parti) Özet Şemaları ──────────────────────────────────────────

class BatchInfo(BaseModel):
    """Tek bir partinin özet bilgisi."""
    batch_id: UUID
    batch_number: str | None
    quantity: float
    expiry_date: date | None
    days_until_expiry: int | None
    is_low_stock: bool

class BatchSummary(BaseModel):
    """Aynı isimdeki ürünün tüm partilerini özetler (FEFO mantığıyla)."""
    name: str
    category: str | None
    unit: str | None
    total_quantity: float
    total_min_stock: float
    is_low_stock: bool
    nearest_expiry_date: date | None
    days_until_nearest_expiry: int | None
    batches: list[BatchInfo]
