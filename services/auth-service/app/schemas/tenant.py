"""
Pydantic şeması: Tenant / Clinic CRUD
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ClinicSettingsSchema(BaseModel):
    """Klinik ayarları — genişletilebilir JSONB alanı."""
    logo_url: str | None = None
    address: str | None = None
    phone: str | None = None
    working_hours: dict[str, Any] | None = None
    whatsapp_enabled: bool = True
    timezone: str = "Europe/Istanbul"


class ClinicResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    code: str | None = None
    email_domain: str | None = None
    settings: dict[str, Any]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ClinicUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    settings: ClinicSettingsSchema | None = None
