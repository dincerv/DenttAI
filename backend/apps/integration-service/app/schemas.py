"""
Pydantic şemaları — Integration Service.

Harici sistemlerin (DentSoft vb.) gönderdiği veriler bu şemalarla
valide edilir. Alan adları kasıtlı olarak toleranslı tutulmuştur;
eksik opsiyonel alanlar None olarak geçer.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Hasta Satırı (harici format) ───────────────────────────

class ExternalPatient(BaseModel):
    """
    Harici sistemden gelen tek hasta satırı.
    full_name ZORUNLU; geri kalan alanlar opsiyonel.
    """
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, v: object) -> str | None:
        if v is None or (isinstance(v, float)):
            return None
        s = str(v).strip()
        # Boş stringleri None yap
        return s if s else None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        return s if s else None


# ── Toplu İçe Aktarma İsteği (JSON) ───────────────────────

class PatientImportRequest(BaseModel):
    patients: list[ExternalPatient] = Field(..., min_length=1, max_length=5000)


# ── Sonuç Şeması ──────────────────────────────────────────

class ImportResult(BaseModel):
    total_received:  int
    inserted:        int
    skipped_duplicates: int
    skipped_invalid: int
    errors:          list[str] = Field(default_factory=list)


# ── DentSoft Randevu Satırı (opsiyonel ileri mapping) ─────

class ExternalAppointment(BaseModel):
    patient_phone: str | None = None
    patient_name:  str
    doctor_name:   str
    scheduled_at:  str          # ISO 8601 string — servis tarafı parse eder
    specialty:     str | None = None
    notes:         str | None = None


# ── Entegrasyon Konfigürasyon Şemaları ─────────────────────

class IntegrationConfigCreate(BaseModel):
    """Yeni entegrasyon bağlantısı oluşturma."""
    provider: str = Field(..., pattern=r"^(dentsoft|drdentes)$")
    display_name: str = Field(..., min_length=1, max_length=100)
    config: dict = Field(default_factory=dict, description="base_url, api_key gibi bağlantı bilgileri")
    sync_interval_minutes: int = Field(default=30, ge=5, le=1440)


class IntegrationConfigUpdate(BaseModel):
    """Mevcut entegrasyon güncelleme."""
    display_name: str | None = None
    config: dict | None = None
    is_active: bool | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=5, le=1440)


class IntegrationConfigResponse(BaseModel):
    id: str
    clinic_id: str
    provider: str
    display_name: str
    is_active: bool
    has_session_cookie: bool = False
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_message: str | None
    sync_interval_minutes: int
    created_at: datetime | None
    updated_at: datetime | None


class SyncResultResponse(BaseModel):
    provider: str
    patients_pulled: int = 0
    patients_inserted: int = 0
    appointments_pulled: int = 0
    appointments_inserted: int = 0
    doctors_pulled: int = 0
    errors: list[str] = Field(default_factory=list)
    synced_at: datetime | None = None


class TestConnectionResponse(BaseModel):
    provider: str
    success: bool
    message: str


class SessionCookieUpdate(BaseModel):
    """Oturum çerezi güncelleme."""
    session_cookie: str = Field(..., min_length=10, max_length=5000)


class LocalDoctorSummary(BaseModel):
    id: str
    full_name: str
    specialty: str | None = None


class ExternalDoctorSummary(BaseModel):
    external_name: str
    mapped_doctor_id: str | None = None


class DoctorMappingResponse(BaseModel):
    local_doctors: list[LocalDoctorSummary] = Field(default_factory=list)
    external_doctors: list[ExternalDoctorSummary] = Field(default_factory=list)


class DoctorMappingUpdate(BaseModel):
    mappings: dict[str, str | None] = Field(default_factory=dict)
