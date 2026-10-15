"""
Pydantic şemaları — Integration Service.

Harici sistemlerin (DentSoft vb.) gönderdiği veriler bu şemalarla
valide edilir. Alan adları kasıtlı olarak toleranslı tutulmuştur;
eksik opsiyonel alanlar None olarak geçer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Hasta Satırı (harici format) ───────────────────────────

class ExternalClinicalVisit(BaseModel):
    """Dentsoft randevu/tedavi satırı → DentAI tedavi + not."""
    external_ref: str | None = Field(None, max_length=64)
    when_text: str | None = Field(None, max_length=120)
    doctor: str | None = Field(None, max_length=120)
    tooth_hint: str | None = Field(None, max_length=20)
    procedure_raw: str | None = Field(None, max_length=120)
    procedure: str | None = Field(None, max_length=30)
    status: str | None = Field(None, max_length=20)
    note: str | None = Field(None, max_length=500)

    @field_validator("procedure", mode="before")
    @classmethod
    def normalize_procedure(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        allowed = {
            "muayene", "dolgu", "kanal", "cekim", "kron", "kopru",
            "implant", "protez", "veneer", "ortodonti", "temizlik", "diger",
        }
        return s if s in allowed else "diger"

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if s in ("planned", "completed", "cancelled"):
            return s
        return "completed"


class ExternalPatient(BaseModel):
    """
    Harici sistemden gelen tek hasta satırı.
    full_name ZORUNLU; geri kalan alanlar opsiyonel.
    """
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    national_id: str | None = Field(None, max_length=11)
    birth_date: str | None = Field(None, max_length=16)
    insurance_type: str | None = Field(None, max_length=20)
    insurance_provider: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)
    sex: str | None = Field(None, max_length=20)
    address: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    external_id: str | None = Field(None, max_length=128)
    avatar_url: str | None = Field(None, max_length=500)
    file_number: str | None = Field(None, max_length=64)
    archive_number: str | None = Field(None, max_length=64)
    occupation: str | None = Field(None, max_length=100)
    nationality: str | None = Field(None, max_length=100)
    blood_type: str | None = Field(None, max_length=20)
    clinical_visits: list[ExternalClinicalVisit] = Field(default_factory=list, max_length=50)

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

    @field_validator("national_id", mode="before")
    @classmethod
    def normalize_tc(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().split(".")[0]
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return None
        if len(digits) != 11:
            raise ValueError("TC 11 haneli olmali")
        return digits

    @field_validator("insurance_type", mode="before")
    @classmethod
    def normalize_insurance(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s:
            return None
        aliases = {
            "sgk": "sgk",
            "bagkur": "sgk",
            "emekli": "sgk",
            "ozel": "private",
            "private": "private",
            "karma": "mixed",
            "mixed": "mixed",
            "yok": "none",
            "none": "none",
        }
        return aliases.get(s, "none")

    @field_validator("sex", mode="before")
    @classmethod
    def normalize_sex(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s:
            return None
        aliases = {
            "1": "female",
            "f": "female",
            "female": "female",
            "kadin": "female",
            "kadın": "female",
            "k": "female",
            "0": "male",
            "2": "male",
            "m": "male",
            "male": "male",
            "erkek": "male",
            "e": "male",
            "other": "other",
            "diger": "other",
            "diğer": "other",
            "unknown": "unknown",
            "bilinmiyor": "unknown",
        }
        return aliases.get(s, "unknown")

    @field_validator("address", "city", "district", "country", "external_id", "avatar_url", "file_number", "archive_number", "occupation", "nationality", "blood_type", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


# ── Toplu İçe Aktarma İsteği (JSON) ───────────────────────

class PatientImportRequest(BaseModel):
    patients: list[ExternalPatient] = Field(..., min_length=1, max_length=5000)


# ── Sonuç Şeması ──────────────────────────────────────────

class ImportResult(BaseModel):
    total_received:  int
    inserted:        int
    updated:         int = 0
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


# ── PMS takvim senkronu (tarayıcı eklentisi) ──────────────

AppointmentStatusLiteral = Literal["scheduled", "confirmed", "cancelled", "completed", "no_show"]


class PmsDoctorIn(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)


class PmsAppointmentIn(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=128)
    start: datetime
    end: datetime | None = None
    doctor_external_id: str | None = Field(None, max_length=128)
    doctor_name: str | None = Field(None, max_length=255)
    patient_external_id: str | None = Field(None, max_length=128)
    patient_name: str = Field(..., min_length=2, max_length=255)
    patient_phone: str | None = Field(None, max_length=20)
    treatment: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)
    status: AppointmentStatusLiteral = "scheduled"
    is_new_patient: bool | None = None

    @field_validator(
        "doctor_external_id", "doctor_name", "patient_external_id", "patient_phone", "treatment", "notes",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class PmsAppointmentImportRequest(BaseModel):
    source: Literal["dentsoft", "drdentes"] = "dentsoft"
    doctors: list[PmsDoctorIn] = Field(default_factory=list, max_length=500)
    appointments: list[PmsAppointmentIn] = Field(default_factory=list, max_length=1000)


class PmsAppointmentImportResult(BaseModel):
    total_received: int
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_invalid: int = 0
    patients_created: int = 0
    doctors_created: int = 0
    errors: list[str] = Field(default_factory=list)


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
