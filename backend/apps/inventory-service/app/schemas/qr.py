"""Pydantic şemaları: QR kod üretimi ve aktivasyonu."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class QRGenerateRequest(BaseModel):
    name: str = Field(..., max_length=255, description="Malzeme adı")
    category: str | None = Field(None, max_length=100)
    expected_lifespan: int | None = Field(None, gt=0, description="Beklenen ömür (gün)")


class QRGenerateResponse(BaseModel):
    qr_id: str
    shelf_code: str = Field(..., description="Gözle okunabilir kısa raf kodu (ABC-123)")
    material_id: UUID
    qr_code_base64: str = Field(..., description="PNG formatında base64 kodlanmış QR resmi")

    model_config = {"from_attributes": True}


class QRActivateRequest(BaseModel):
    qr_id: str = Field(..., description="Aktivasyon yapılacak QR ID")


class QRActivateResponse(BaseModel):
    qr_id: str
    material_id: UUID
    message: str = "Malzeme kullanıma alındı"

    model_config = {"from_attributes": True}
