"""
Pydantic Schemas: WhatsApp Entegrasyonu ve AI Yedek Liste Yönetimi API Request/Response Modelleri

Production-ready validation ve serialization.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# ═══════════════════════════════════════════════════════════════════════════════
# CLINIC SETTINGS SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ReminderInterval(BaseModel):
    """Bildirim aralığı."""
    hours_before: Optional[int] = Field(None, ge=0)
    days_before: Optional[int] = Field(None, ge=0)
    channel: str = Field(default="whatsapp")
    enabled: bool = Field(default=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "hours_before": 24,
                "channel": "whatsapp",
                "enabled": True,
            }
        }


class PostOpFollowupInterval(BaseModel):
    """Post-op takip aralığı."""
    hours_after: Optional[int] = Field(None, ge=0)
    days_after: Optional[int] = Field(None, ge=0)
    template_key: str
    enabled: bool = Field(default=True)
    priority: str = Field(default="medium")  # low, medium, high


class ClinicSettingsCreate(BaseModel):
    """Yeni klinik ayarları oluştur."""
    reminder_intervals: Optional[dict[str, Any]] = Field(None)
    post_op_followup_intervals: Optional[list[PostOpFollowupInterval]] = Field(None)
    is_whatsapp_enabled: bool = Field(default=False)
    whatsapp_business_account_id: Optional[str] = Field(None)
    whatsapp_phone_number_id: Optional[str] = Field(None)
    whatsapp_template_lang: str = Field(default="tr")
    do_not_disturb_start: Optional[str] = Field(None)  # "22:00"
    do_not_disturb_end: Optional[str] = Field(None)  # "08:00"


class ClinicSettingsUpdate(BaseModel):
    """Klinik ayarlarını güncelle."""
    reminder_intervals: Optional[dict[str, Any]] = Field(None)
    post_op_followup_intervals: Optional[list[PostOpFollowupInterval]] = Field(None)
    is_whatsapp_enabled: Optional[bool] = Field(None)
    whatsapp_business_account_id: Optional[str] = Field(None)
    whatsapp_phone_number_id: Optional[str] = Field(None)
    whatsapp_template_lang: Optional[str] = Field(None)
    do_not_disturb_start: Optional[str] = Field(None)
    do_not_disturb_end: Optional[str] = Field(None)


class ClinicSettingsResponse(BaseModel):
    """Klinik ayarları yanıtı."""
    id: UUID
    clinic_id: UUID
    reminder_intervals: Optional[dict[str, Any]]
    post_op_followup_intervals: Optional[list[PostOpFollowupInterval]]
    is_whatsapp_enabled: bool
    whatsapp_business_account_id: Optional[str]
    whatsapp_phone_number_id: Optional[str]
    whatsapp_template_lang: str
    do_not_disturb_start: Optional[str]
    do_not_disturb_end: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR SETTINGS SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorSettingsCreate(BaseModel):
    """Yeni doktor ayarları oluştur."""
    doctor_id: UUID
    receive_emergency_alerts: bool = Field(default=True)
    preferred_notification_channel: str = Field(default="whatsapp")
    waitlist_auto_fill_enabled: bool = Field(default=True)
    ai_mutation_score_threshold: float = Field(default=75.0, ge=0, le=100)
    timezone: str = Field(default="Europe/Istanbul")


class DoctorSettingsUpdate(BaseModel):
    """Doktor ayarlarını güncelle."""
    receive_emergency_alerts: Optional[bool] = Field(None)
    preferred_notification_channel: Optional[str] = Field(None)
    waitlist_auto_fill_enabled: Optional[bool] = Field(None)
    ai_mutation_score_threshold: Optional[float] = Field(None, ge=0, le=100)
    timezone: Optional[str] = Field(None)


class DoctorSettingsResponse(BaseModel):
    """Doktor ayarları yanıtı."""
    id: UUID
    clinic_id: UUID
    doctor_id: UUID
    receive_emergency_alerts: bool
    preferred_notification_channel: str
    waitlist_auto_fill_enabled: bool
    ai_mutation_score_threshold: float
    timezone: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# CLINIC FAQ SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicFaqCreate(BaseModel):
    """Yeni klinik SSS'i oluştur."""
    question: str = Field(..., min_length=10, max_length=500)
    answer: str = Field(..., min_length=20)
    category: str = Field(..., min_length=3)  # post_op, general, emergency, vb.
    priority: int = Field(default=10, ge=1, le=100)
    video_url: Optional[str] = Field(None)
    attachment_urls: Optional[list[str]] = Field(None)
    whatsapp_template_key: Optional[str] = Field(None)
    status: str = Field(default="draft")  # draft, published, archived


class ClinicFaqUpdate(BaseModel):
    """Klinik SSS'ini güncelle."""
    question: Optional[str] = Field(None, min_length=10, max_length=500)
    answer: Optional[str] = Field(None, min_length=20)
    category: Optional[str] = Field(None)
    priority: Optional[int] = Field(None, ge=1, le=100)
    video_url: Optional[str] = Field(None)
    attachment_urls: Optional[list[str]] = Field(None)
    whatsapp_template_key: Optional[str] = Field(None)
    status: Optional[str] = Field(None)


class ClinicFaqResponse(BaseModel):
    """Klinik SSS'i yanıtı."""
    id: UUID
    clinic_id: UUID
    question: str
    answer: str
    category: str
    priority: int
    video_url: Optional[str]
    attachment_urls: Optional[list[str]]
    whatsapp_template_key: Optional[str]
    status: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# PATIENT FEEDBACK SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class PatientFeedbackCreate(BaseModel):
    """Yeni hasta geri bildirimi oluştur."""
    appointment_id: UUID
    patient_id: UUID
    feedback_type: str  # pain, swelling, bleeding, infection, satisfaction, other
    severity: str  # low, medium, high, critical
    message: str = Field(..., min_length=5)
    image_urls: Optional[list[str]] = Field(None)
    channel: str = Field(default="whatsapp")


class PatientFeedbackUpdate(BaseModel):
    """Hasta geri bildirimi güncelle."""
    severity: Optional[str] = Field(None)
    message: Optional[str] = Field(None)
    requires_action: Optional[bool] = Field(None)
    action_required_details: Optional[str] = Field(None)
    assigned_to_user_id: Optional[UUID] = Field(None)
    resolution_notes: Optional[str] = Field(None)
    is_resolved: Optional[bool] = Field(None)


class PatientFeedbackResponse(BaseModel):
    """Hasta geri bildirimi yanıtı."""
    id: UUID
    clinic_id: UUID
    appointment_id: UUID
    patient_id: UUID
    doctor_id: Optional[UUID]
    feedback_type: str
    severity: str
    message: str
    image_urls: Optional[list[str]]
    requires_action: bool
    action_required_details: Optional[str]
    assigned_to_user_id: Optional[UUID]
    resolution_notes: Optional[str]
    is_resolved: bool
    resolved_at: Optional[datetime]
    channel: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PatientFeedbackListResponse(BaseModel):
    """Hasta geri bildirimi listesi yanıtı (pagination)."""
    total: int
    page: int
    per_page: int
    items: list[PatientFeedbackResponse]


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP MESSAGE LOG SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappMessageCreate(BaseModel):
    """WhatsApp mesaj gönder."""
    patient_id: Optional[UUID] = Field(None)
    phone_number: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    message_type: str  # reminder, post_op, emergency, faq
    template_key: str
    template_variables: Optional[dict[str, Any]] = Field(None)


class WhatsappMessageResponse(BaseModel):
    """WhatsApp mesaj yanıtı."""
    id: UUID
    clinic_id: UUID
    patient_id: Optional[UUID]
    phone_number: str
    message_type: str
    template_key: str
    status: str  # queued, sent, delivered, read, failed
    whatsapp_message_id: Optional[str]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WhatsappMessageMetrics(BaseModel):
    """WhatsApp metrikler."""
    total_sent: int
    total_delivered: int
    total_read: int
    total_failed: int
    delivery_rate: float  # 0-100
    read_rate: float  # 0-100
    failure_rate: float  # 0-100
    average_retries: float


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOUND SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicIntegrationStatus(BaseModel):
    """Klinik WhatsApp entegrasyon durumu."""
    clinic_id: UUID
    is_whatsapp_enabled: bool
    message_quota_remaining: int
    doctors_configured: int
    faq_count: int
    pending_feedback_count: int
    last_message_sent_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR RESPONSE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """Hata yanıtı."""
    error: str
    detail: Optional[str] = Field(None)
    request_id: Optional[UUID] = Field(None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


__all__ = [
    # Clinic Settings
    "ReminderInterval",
    "PostOpFollowupInterval",
    "ClinicSettingsCreate",
    "ClinicSettingsUpdate",
    "ClinicSettingsResponse",
    
    # Doctor Settings
    "DoctorSettingsCreate",
    "DoctorSettingsUpdate",
    "DoctorSettingsResponse",
    
    # Clinic FAQ
    "ClinicFaqCreate",
    "ClinicFaqUpdate",
    "ClinicFaqResponse",
    
    # Patient Feedback
    "PatientFeedbackCreate",
    "PatientFeedbackUpdate",
    "PatientFeedbackResponse",
    "PatientFeedbackListResponse",
    
    # WhatsApp
    "WhatsappMessageCreate",
    "WhatsappMessageResponse",
    "WhatsappMessageMetrics",
    
    # Compound
    "ClinicIntegrationStatus",
    "ErrorResponse",
]
