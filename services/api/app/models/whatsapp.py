"""
SQLAlchemy modelleri: WhatsApp Entegrasyonu ve AI Yedek Liste Yönetimi.

Production-ready implementations for:
- ClinicSettings: Bildirim ve takip aralıkları
- DoctorSettings: Doktor ayarları
- AppointmentExtended: AI metadata
- ClinicFaq: RAG entegrasyonu
- PatientFeedback: Hasta geri bildirimi
- WhatsappMessageLog: Audit trail

Tüm modeller SQLAlchemy ORM ve PostgreSQL native types kullanır.
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

from app.core.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CLINIC SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicSettings(Base):
    """
    Klinik bazlı ayarlar: bildirim aralıkları ve post-op takip zamanlaması.
    
    reminder_intervals örneği:
    {
        "appointment_reminder": [
            {"hours_before": 24, "channel": "whatsapp", "enabled": true},
            {"hours_before": 2, "channel": "whatsapp", "enabled": true}
        ],
        "post_op_followup": [
            {"hours_after": 2, "template_key": "post_op_pain_check", "enabled": true},
            {"days_after": 1, "template_key": "post_op_recovery_status", "enabled": true},
            {"days_after": 7, "template_key": "post_op_final_check", "enabled": true}
        ]
    }
    
    post_op_followup_intervals (backcompat):
    [
        {"hours_after": 2, "enabled": true, "priority": "high"},
        {"days_after": 1, "enabled": true, "priority": "medium"},
        {"days_after": 7, "enabled": true, "priority": "low"}
    ]
    """
    __tablename__ = "clinic_settings"
    __table_args__ = (
        Index("idx_clinic_settings_clinic_id", "clinic_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # JSONB: remindeler'in zamanlaması
    reminder_intervals: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    # JSONB: post-op takip aralıkları (explicit)
    post_op_followup_intervals: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    # WhatsApp enable/disable
    is_whatsapp_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    whatsapp_business_account_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # Şablon dil: "tr", "en", vb.
    whatsapp_template_lang: Mapped[str] = mapped_column(
        String(10), default="tr", nullable=False
    )
    # İletişim saatleri (isteğe bağlı)
    do_not_disturb_start: Mapped[str | None] = mapped_column(
        String(5), nullable=True  # "22:00"
    )
    do_not_disturb_end: Mapped[str | None] = mapped_column(
        String(5), nullable=True  # "08:00"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DOCTOR SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorSettings(Base):
    """
    Doktor bazlı bildirim ve AI ayarları.
    
    receive_emergency_alerts: Hasta acil şikayetleri için gerçek zamanlı alert?
    preferred_notification_channel: "whatsapp" | "sms" | "email"
    ai_mutation_score_threshold: AI'ın doktora slot teklifi sunacağı eşik (0-100)
    waitlist_auto_fill_enabled: AI otomatis slot doldursun mu?
    """
    __tablename__ = "doctor_settings"
    __table_args__ = (
        Index("idx_doctor_settings_doctor_id", "doctor_id"),
        Index("idx_doctor_settings_clinic_id", "clinic_id"),
        UniqueConstraint("clinic_id", "doctor_id", name="uq_doctor_clinic_settings"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    # Acil alertler aktif mi?
    receive_emergency_alerts: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    # Tercih edilen kanal
    preferred_notification_channel: Mapped[str] = mapped_column(
        String(20), default="whatsapp", nullable=False
    )
    # Yedek liste otomasiyon yönetimi
    waitlist_auto_fill_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    # AI skor eşiği (0-100)
    ai_mutation_score_threshold: Mapped[float] = mapped_column(
        Float, default=75.0, nullable=False
    )
    # Saat dilimi (opsiyonel)
    timezone: Mapped[str] = mapped_column(
        String(50), default="Europe/Istanbul", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. APPOINTMENT EXTENDED
# ═══════════════════════════════════════════════════════════════════════════════

class AppointmentExtended(Base):
    """
    Mevcut Appointment'ı genişleten AI metadata.
    
    is_auto_filled_by_ai: AI tarafından yedek listeden dolduruldu mu?
    ai_mutation_score: AI'ın hasta tercihini skorladığı değer (0-100)
    ai_ranking_reason: AI'ın bu hasayı seçme sebebi (model transparency)
    """
    __tablename__ = "appointment_extended"
    __table_args__ = (
        Index("idx_appointment_extended_appointment_id", "appointment_id", unique=True),
        Index("idx_appointment_extended_clinic_id", "clinic_id"),
        Index("idx_appointment_extended_ai_filled", "is_auto_filled_by_ai"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    appointment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # AI tarafından dolduruldu mu?
    is_auto_filled_by_ai: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # AI'ın verdiği skor (0-100)
    ai_mutation_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    # AI'ın karını açıklaması (transparency)
    ai_ranking_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # AI seçtiği hasta ID (eğer auto-filled)
    ai_selected_patient_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CLINIC FAQ (RAG)
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicFaqStatus(str, enum.Enum):
    """FAQ yayınlama durumu."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ClinicFaq(Base):
    """
    Klinik SSS: RAG (Retrieval-Augmented Generation) için.
    
    Hasta botunun sorularına yanıt vermesi için klinik-spesifik bilgi tabanı.
    
    Örnek SSS:
    - Question: "Diş çekişinden sonra ne yapmalıyım?"
    - Answer: "24 saat ağız çalkalamayın, ağrı kesici kullanın..."
    - Category: "post_op"
    - Video URL: "https://youtube.com/..."
    """
    __tablename__ = "clinic_faq"
    __table_args__ = (
        Index("idx_clinic_faq_clinic_id", "clinic_id"),
        Index("idx_clinic_faq_category", "category"),
        Index("idx_clinic_faq_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # SSS başlığı
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    # Detaylı yanıt
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # Kategori: "post_op", "general", "emergency", "treatment_info"
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    # Görünüm önceliği (düşük = yüksek)
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    # Eğitim vidyosu
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Ek dosyalar (PDF, görüntü vb.)
    attachment_urls: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    # WhatsApp şablonuna bağlantı
    whatsapp_template_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # Yayınlama durumu
    status: Mapped[ClinicFaqStatus] = mapped_column(
        Enum(ClinicFaqStatus, name="clinic_faq_status", create_type=False),
        default=ClinicFaqStatus.DRAFT,
        nullable=False,
    )
    # Kimin tarafından oluşturuldu
    created_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PATIENT FEEDBACK
# ═══════════════════════════════════════════════════════════════════════════════

class PatientFeedbackType(str, enum.Enum):
    """Şikayet tipi."""
    PAIN = "pain"
    SWELLING = "swelling"
    BLEEDING = "bleeding"
    INFECTION = "infection"
    SATISFACTION = "satisfaction"
    OTHER = "other"


class PatientFeedbackSeverity(str, enum.Enum):
    """Önem derecesi."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatientFeedback(Base):
    """
    Hasta tedavi sonrası geri bildirimi: ağrı, şişme, enfeksiyon vb.
    
    Örnek akış:
    1. Randevu sonrasında AI hasta WhatsApp'a: "Şu anda nasılsınız? Ağrı var mı?"
    2. Hasta cevap verir
    3. Sistem PatientFeedback kaydı oluşturur
    4. Doktor/AI bunu inceleyerek gerekli eylemi seçer
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

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # İlişkili randevu
    appointment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    # Hasta kimliği
    patient_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    # Sorumlu doktor (isteğe bağlı)
    doctor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # Şikayet tipi
    feedback_type: Mapped[PatientFeedbackType] = mapped_column(
        Enum(PatientFeedbackType, name="patient_feedback_type", create_type=False),
        nullable=False,
    )
    # Önem derecesi
    severity: Mapped[PatientFeedbackSeverity] = mapped_column(
        Enum(PatientFeedbackSeverity, name="patient_feedback_severity", create_type=False),
        nullable=False,
    )
    # Hasta açıklaması
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Hasta tarafından gönderilen görüntüler
    image_urls: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    # Doktor müdahalesi gerekiyor mu?
    requires_action: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Doktor için notlar (AI tarafından eklenebilir)
    action_required_details: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Atanan kullanıcı (follow-up için)
    assigned_to_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # Çözüm notları
    resolution_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Çözüldü mü?
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Çözüm zamanı
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Hangi kanal üzerinden? ("whatsapp", "call", "sms")
    channel: Mapped[str] = mapped_column(
        String(20), default="whatsapp", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. WHATSAPP MESSAGE LOG
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappMessageStatus(str, enum.Enum):
    """Mesaj durumu."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class WhatsappMessageLog(Base):
    """
    WhatsApp mesaj takibi: idempotency, retry, deliverability ve audit trail.
    
    Her mesaj:
    - Unique idempotency_key ile duplicate prevention
    - Status tracking (queued -> sent -> delivered -> read)
    - Retry mekanizması (exponential backoff)
    - Hata kaydı
    """
    __tablename__ = "whatsapp_message_log"
    __table_args__ = (
        Index("idx_whatsapp_message_log_clinic_id", "clinic_id"),
        Index("idx_whatsapp_message_log_patient_id", "patient_id"),
        Index("idx_whatsapp_message_log_status", "status"),
        Index("idx_whatsapp_message_log_idempotency_key", "idempotency_key"),
        UniqueConstraint("clinic_id", "idempotency_key", name="uq_whatsapp_idempotency"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Güvenilir hasta referansı
    patient_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # Telefon numarası (WhatsApp gerektiriyor)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    # Mesaj tipi: "reminder", "post_op", "emergency", "faq"
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Hangi şablon?
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # Idempotency garantisi
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Mesaj durumu
    status: Mapped[WhatsappMessageStatus] = mapped_column(
        Enum(WhatsappMessageStatus, name="whatsapp_message_status", create_type=False),
        default=WhatsappMessageStatus.QUEUED,
        nullable=False,
    )
    # WhatsApp API mesaj ID'si
    whatsapp_message_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # Hata mesajı (başarısız olursa)
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Retry sayısı
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Son retry zamanı
    last_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Şablon parametreleri (Jinja2 template için)
    template_variables: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    # Kimin tarafından başlatıldı? ("system", "scheduled_job", "manual")
    created_by: Mapped[str] = mapped_column(String(50), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ClinicSettings",
    "DoctorSettings",
    "AppointmentExtended",
    "ClinicFaqStatus",
    "ClinicFaq",
    "PatientFeedbackType",
    "PatientFeedbackSeverity",
    "PatientFeedback",
    "WhatsappMessageStatus",
    "WhatsappMessageLog",
]
