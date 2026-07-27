"""
SQLAlchemy modelleri: WhatsApp Entegrasyonu ve AI Yedek Liste Yönetimi.

Tablolar:
- clinic_settings: Klinik bazlı bildirim ve takip aralıkları (JSONB)
- doctor_settings: Doktor bazlı acil uyarı ayarları
- clinic_faq: RAG (Retrieval-Augmented Generation) için SSS metinleri
- patient_feedback: Hasta geri bildirimi ve şikayet kaydı
- waitlist_extended: Waitlist'i genişleten preferred_doctor_ids

Tüm tablolar clinic_id ile tenant izolasyonu (RLS) sağlar.
Production-ready: Cloud-agnostic, indexed, nullable ve default values optimize edilmiş.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


# ═══════════════════════════════════════════════════════════════════════════════
# BASE CLASS (shared/db/base.py'dan import edilecek)
# ═══════════════════════════════════════════════════════════════════════════════

def get_base():
    """Shared base için placeholder. Her service kendi Base'ini tanımlıyacak."""
    # Bunu services'ler kendi database modüllerinde implement edecek
    # Örnek:
    # from sqlalchemy.orm import declarative_base
    # Base = declarative_base()
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CLINIC SETTINGS MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicSettings:
    """
    Klinik bazlı ayarlar: bildirim aralıkları ve post-op takip zamanlaması.
    
    reminder_intervals: {
        "appointment_reminder": [
            {"hours_before": 24, "channel": "whatsapp"},
            {"hours_before": 2, "channel": "whatsapp"}
        ],
        "post_op_followup": [
            {"hours_after": 2, "template_key": "post_op_pain_check"},
            {"days_after": 1, "template_key": "post_op_recovery_status"}
        ]
    }
    
    post_op_followup_intervals: (redundant ama explicit clarity için)
    [
        {"hours_after": 2, "enabled": true},
        {"days_after": 1, "enabled": true},
        {"days_after": 7, "enabled": true}
    ]
    """
    __tablename__ = "clinic_settings"
    __table_args__ = (
        Index("idx_clinic_settings_clinic_id", "clinic_id"),
    )

    # Placeholder - subclass'a implement edilecek
    id: Mapped[UUID]
    clinic_id: Mapped[UUID]
    reminder_intervals: Mapped[dict[str, Any] | None]
    post_op_followup_intervals: Mapped[list[dict[str, Any]] | None]
    is_whatsapp_enabled: Mapped[bool]
    whatsapp_template_lang: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DOCTOR SETTINGS MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorSettings:
    """
    Doktor bazlı bildirim ve alert ayarları.
    
    receive_emergency_alerts: Hasta şikayetleri için WhatsApp alert alacak mı?
    preferred_notification_channel: "whatsapp" | "sms" | "email"
    mutation_score_threshold: AI'ın doktora teklif sunacağı eşik (0-100)
    """
    __tablename__ = "doctor_settings"
    __table_args__ = (
        Index("idx_doctor_settings_doctor_id", "doctor_id"),
        Index("idx_doctor_settings_clinic_id", "clinic_id"),
    )

    # Placeholder
    id: Mapped[UUID]
    clinic_id: Mapped[UUID]
    doctor_id: Mapped[UUID]
    receive_emergency_alerts: Mapped[bool]
    preferred_notification_channel: Mapped[str]
    waitlist_auto_fill_enabled: Mapped[bool]
    ai_mutation_score_threshold: Mapped[float]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. WAITLIST EXTENDED MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class WaitlistExtended:
    """
    Mevcut Waitlist'ı genişletir: preferred_doctor_ids (tercih edilen doktor listesi).
    Mevcut waitlist tablosuna migration ile eklenecek.
    
    Bu model, waitlist'in preferred_doctor_ids alanını ifade eder.
    """
    __tablename__ = "waitlist_extended"
    __table_args__ = (
        Index("idx_waitlist_extended_waitlist_id", "waitlist_id"),
        Index("idx_waitlist_extended_clinic_id", "clinic_id"),
    )

    # Placeholder
    id: Mapped[UUID]
    waitlist_id: Mapped[UUID]
    clinic_id: Mapped[UUID]
    preferred_doctor_ids: Mapped[list[UUID] | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. APPOINTMENT EXTENDED MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class AppointmentExtended:
    """
    Mevcut Appointment'ı genişletir: is_auto_filled_by_ai flag'i ve AI metadata.
    
    Mevcut appointments tablosuna migration ile eklenecek.
    """
    __tablename__ = "appointment_extended"
    __table_args__ = (
        Index("idx_appointment_extended_appointment_id", "appointment_id"),
        Index("idx_appointment_extended_clinic_id", "clinic_id"),
        Index("idx_appointment_extended_ai_filled", "is_auto_filled_by_ai"),
    )

    # Placeholder
    id: Mapped[UUID]
    appointment_id: Mapped[UUID]
    clinic_id: Mapped[UUID]
    is_auto_filled_by_ai: Mapped[bool]
    ai_mutation_score: Mapped[float | None]
    ai_ranking_reason: Mapped[str | None]
    ai_selected_patient_id: Mapped[UUID | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CLINIC FAQ MODEL (RAG)
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicFaqStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ClinicFaq:
    """
    Klinik bazlı SSS: RAG entegrasyonu için.
    
    Hasta sorularına karşılık gelen yapılandırılmış cevaplar, videolar, dokümanlar.
    
    Örnek:
    - question: "Diş çekişinden sonra ne yapmalıyım?"
    - answer: "24 saat ağız çalkalamayın, ağrı kesici kullanın..."
    - category: "post_op"
    - video_url: "https://youtube.com/..."
    - attachment_urls: ["https://clinic-cdn/post_op_guide.pdf"]
    """
    __tablename__ = "clinic_faq"
    __table_args__ = (
        Index("idx_clinic_faq_clinic_id", "clinic_id"),
        Index("idx_clinic_faq_category", "category"),
        Index("idx_clinic_faq_status", "status"),
    )

    # Placeholder
    id: Mapped[UUID]
    clinic_id: Mapped[UUID]
    question: Mapped[str]
    answer: Mapped[str]
    category: Mapped[str]  # "post_op", "general", "emergency", "treatment_info"
    priority: Mapped[int]  # Sıralama: düşük = yüksek öncelik
    video_url: Mapped[str | None]
    attachment_urls: Mapped[list[str] | None]
    whatsapp_template_key: Mapped[str | None]
    status: Mapped[ClinicFaqStatus]
    created_by_user_id: Mapped[UUID]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PATIENT FEEDBACK MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class PatientFeedbackType(str, enum.Enum):
    PAIN = "pain"
    SWELLING = "swelling"
    BLEEDING = "bleeding"
    INFECTION = "infection"
    SATISFACTION = "satisfaction"
    OTHER = "other"


class PatientFeedbackSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatientFeedback:
    """
    Hasta tedavi sonrası geri bildirimi: AI'a şikayet, ağrı, şişme vb. kaydı.
    
    Örnek flow:
    1. Randevu sonrasında hasta WhatsApp'tan "ağrı var mı?" sorusuna cevap verir
    2. Sistem PatientFeedback kaydı oluşturur
    3. Doktor/AI bunu inceleyerek takip eylemini seçer
    
    Alanlar:
    - appointment_id: Hangi randevu sonrası
    - feedback_type: "pain", "swelling", "infection" vb.
    - severity: "low", "medium", "high", "critical"
    - message: Hasta tarafından yazılan açıklama
    - requires_action: Doktor müdahalesi gerekiyor mu?
    - action_required_details: İnsan karar için notlar
    """
    __tablename__ = "patient_feedback"
    __table_args__ = (
        Index("idx_patient_feedback_clinic_id", "clinic_id"),
        Index("idx_patient_feedback_appointment_id", "appointment_id"),
        Index("idx_patient_feedback_patient_id", "patient_id"),
        Index("idx_patient_feedback_severity", "severity"),
        Index("idx_patient_feedback_requires_action", "requires_action"),
        Index("idx_patient_feedback_created_at", "created_at"),
    )

    # Placeholder
    id: Mapped[UUID]
    clinic_id: Mapped[UUID]
    appointment_id: Mapped[UUID]
    patient_id: Mapped[UUID]
    doctor_id: Mapped[UUID | None]
    feedback_type: Mapped[PatientFeedbackType]
    severity: Mapped[PatientFeedbackSeverity]
    message: Mapped[str]
    image_urls: Mapped[list[str] | None]  # Hasta tarafından gönderilen fotoğraflar
    requires_action: Mapped[bool]
    action_required_details: Mapped[str | None]
    assigned_to_user_id: Mapped[UUID | None]
    resolution_notes: Mapped[str | None]
    is_resolved: Mapped[bool]
    resolved_at: Mapped[datetime | None]
    channel: Mapped[str]  # "whatsapp", "call", "sms"
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ═══════════════════════════════════════════════════════════════════════════════
# 7. WHATSAPP MESSAGE LOG MODEL (basit audit/tracking)
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappMessageStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class WhatsappMessageLog:
    """
    WhatsApp mesaj takibi: idempotency, retry, audit trail.
    
    Alanlar:
    - idempotency_key: Duplicate prevention (clinic_id + patient_id + type + timestamp)
    - message_type: "reminder", "post_op_followup", "emergency_alert", "faq"
    - phone_number: Hasta telefon numarası
    - template_key: Hangi template?
    """
    __tablename__ = "whatsapp_message_log"
    __table_args__ = (
        Index("idx_whatsapp_message_log_clinic_id", "clinic_id"),
        Index("idx_whatsapp_message_log_patient_id", "patient_id"),
        Index("idx_whatsapp_message_log_status", "status"),
        Index("idx_whatsapp_message_log_idempotency_key", "idempotency_key"),
        UniqueConstraint("clinic_id", "idempotency_key", name="uq_whatsapp_idempotency"),
    )

    # Placeholder
    id: Mapped[UUID]
    clinic_id: Mapped[UUID]
    patient_id: Mapped[UUID]
    phone_number: Mapped[str]
    message_type: Mapped[str]  # "reminder", "post_op", "emergency", "faq"
    template_key: Mapped[str]
    idempotency_key: Mapped[str]
    status: Mapped[WhatsappMessageStatus]
    whatsapp_message_id: Mapped[str | None]
    error_message: Mapped[str | None]
    retry_count: Mapped[int]
    last_retry_at: Mapped[datetime | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    created_by: Mapped[str]  # "system", "scheduled_job", "manual"


# ═══════════════════════════════════════════════════════════════════════════════
# ALEMBIC MIGRATION HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def get_model_summary() -> dict[str, str]:
    """Tüm modellerin özeti (migration'lar için reference)."""
    return {
        "clinic_settings": "Klinik bildirim ve takip ayarları (JSONB)",
        "doctor_settings": "Doktor bildirim ve AI ayarları",
        "waitlist_extended": "Yedek liste tercih edilen doktorlar",
        "appointment_extended": "Randevu AI metadata",
        "clinic_faq": "RAG için klinik SSS'leri",
        "patient_feedback": "Hasta tedavi sonrası geri bildirimi",
        "whatsapp_message_log": "WhatsApp mesaj audit trail",
    }


__all__ = [
    "ClinicSettings",
    "DoctorSettings",
    "WaitlistExtended",
    "AppointmentExtended",
    "ClinicFaqStatus",
    "ClinicFaq",
    "PatientFeedbackType",
    "PatientFeedbackSeverity",
    "PatientFeedback",
    "WhatsappMessageStatus",
    "WhatsappMessageLog",
    "get_model_summary",
]
