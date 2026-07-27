"""
WhatsApp Entegrasyonu ve AI Yedek Liste Yönetimi Business Logic Services

Cloud-agnostic, dependency injection friendly, fully testable.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.whatsapp import (
    ClinicSettings,
    DoctorSettings,
    ClinicFaq,
    PatientFeedback,
    PatientFeedbackSeverity,
    WhatsappMessageLog,
    WhatsappMessageStatus,
)
from app.schemas_whatsapp import (
    ClinicSettingsCreate,
    ClinicSettingsUpdate,
    DoctorSettingsCreate,
    ClinicFaqCreate,
    PatientFeedbackCreate,
    PatientFeedbackUpdate,
    WhatsappMessageCreate,
    WhatsappMessageResponse,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CLINIC SETTINGS SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicSettingsService:
    """Klinik bildirim ve takip ayarları yönetimi."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create(self, clinic_id: UUID) -> ClinicSettings:
        """Klinik ayarlarını al veya oluştur."""
        result = await self.db.execute(
            select(ClinicSettings).where(ClinicSettings.clinic_id == clinic_id)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = ClinicSettings(clinic_id=clinic_id)
            self.db.add(settings)
            await self.db.flush()
        
        return settings
    
    async def update(
        self, clinic_id: UUID, data: ClinicSettingsUpdate
    ) -> ClinicSettings:
        """Klinik ayarlarını güncelle."""
        settings = await self.get_or_create(clinic_id)
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)
        
        settings.updated_at = datetime.utcnow()
        await self.db.flush()
        return settings


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR SETTINGS SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorSettingsService:
    """Doktor bildirim ve AI ayarları yönetimi."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create(
        self, clinic_id: UUID, doctor_id: UUID
    ) -> DoctorSettings:
        """Doktor ayarlarını al veya oluştur."""
        result = await self.db.execute(
            select(DoctorSettings).where(
                and_(
                    DoctorSettings.clinic_id == clinic_id,
                    DoctorSettings.doctor_id == doctor_id,
                )
            )
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = DoctorSettings(clinic_id=clinic_id, doctor_id=doctor_id)
            self.db.add(settings)
            await self.db.flush()
        
        return settings
    
    async def create(
        self, clinic_id: UUID, data: DoctorSettingsCreate
    ) -> DoctorSettings:
        """Yeni doktor ayarları oluştur."""
        data.clinic_id = clinic_id
        settings = DoctorSettings(**data.model_dump())
        self.db.add(settings)
        await self.db.flush()
        return settings
    
    async def update(
        self, clinic_id: UUID, doctor_id: UUID, data: DoctorSettingsUpdate
    ) -> DoctorSettings:
        """Doktor ayarlarını güncelle."""
        settings = await self.get_or_create(clinic_id, doctor_id)
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)
        
        settings.updated_at = datetime.utcnow()
        await self.db.flush()
        return settings


# ═══════════════════════════════════════════════════════════════════════════════
# CLINIC FAQ SERVICE (RAG)
# ═══════════════════════════════════════════════════════════════════════════════

class ClinicFaqService:
    """Klinik SSS (RAG entegrasyonu) yönetimi."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self, clinic_id: UUID, data: ClinicFaqCreate, created_by_user_id: UUID
    ) -> ClinicFaq:
        """Yeni SSS oluştur."""
        faq = ClinicFaq(
            clinic_id=clinic_id,
            created_by_user_id=created_by_user_id,
            **data.model_dump(),
        )
        self.db.add(faq)
        await self.db.flush()
        return faq
    
    async def get_published_by_category(
        self, clinic_id: UUID, category: str
    ) -> list[ClinicFaq]:
        """Yayınlanmış SSS'leri kategoriye göre al."""
        result = await self.db.execute(
            select(ClinicFaq).where(
                and_(
                    ClinicFaq.clinic_id == clinic_id,
                    ClinicFaq.category == category,
                    ClinicFaq.status == "published",
                )
            ).order_by(ClinicFaq.priority)
        )
        return result.scalars().all()
    
    async def search_by_keywords(
        self, clinic_id: UUID, keywords: str, limit: int = 5
    ) -> list[ClinicFaq]:
        """Anahtar kelimelerle SSS ara (RAG için)."""
        # Basit text search - gerçek projede Elasticsearch/PostgreSQL FTS kullanılmalı
        keywords_lower = keywords.lower()
        result = await self.db.execute(
            select(ClinicFaq).where(
                and_(
                    ClinicFaq.clinic_id == clinic_id,
                    ClinicFaq.status == "published",
                )
            ).order_by(ClinicFaq.priority)
        )
        faqs = result.scalars().all()
        
        # Filtered kayıtlar
        scored_faqs = [
            (faq, self._score_relevance(faq, keywords_lower))
            for faq in faqs
        ]
        scored_faqs.sort(key=lambda x: x[1], reverse=True)
        
        return [faq for faq, _ in scored_faqs[:limit]]
    
    @staticmethod
    def _score_relevance(faq: ClinicFaq, keywords: str) -> float:
        """SSS'nin anahtar kelimelerle ilgisini puanlandır."""
        score = 0.0
        
        if keywords in faq.question.lower():
            score += 10.0
        if keywords in faq.answer.lower():
            score += 5.0
        
        # Kelime eşleşmesi
        keyword_list = keywords.split()
        for keyword in keyword_list:
            if keyword in faq.question.lower():
                score += 2.0
            if keyword in faq.answer.lower():
                score += 1.0
        
        return score


# ═══════════════════════════════════════════════════════════════════════════════
# PATIENT FEEDBACK SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class PatientFeedbackService:
    """Hasta geri bildirimi yönetimi ve AI işleme."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self, clinic_id: UUID, data: PatientFeedbackCreate
    ) -> PatientFeedback:
        """Yeni hasta geri bildirimi oluştur."""
        feedback = PatientFeedback(
            clinic_id=clinic_id,
            **data.model_dump(),
        )
        self.db.add(feedback)
        await self.db.flush()
        
        # AI: Şiddet seviyesine göre otomatik action flag'i ayarla
        if feedback.severity in [PatientFeedbackSeverity.CRITICAL, PatientFeedbackSeverity.HIGH]:
            feedback.requires_action = True
        
        await self.db.flush()
        return feedback
    
    async def update(
        self, feedback_id: UUID, data: PatientFeedbackUpdate
    ) -> PatientFeedback:
        """Hasta geri bildirimi güncelle."""
        result = await self.db.execute(
            select(PatientFeedback).where(PatientFeedback.id == feedback_id)
        )
        feedback = result.scalar_one_or_none()
        
        if not feedback:
            raise ValueError(f"Feedback not found: {feedback_id}")
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(feedback, field, value)
        
        # Çözüm zamanı otomatik set et
        if data.is_resolved and not feedback.resolved_at:
            feedback.resolved_at = datetime.utcnow()
        
        feedback.updated_at = datetime.utcnow()
        await self.db.flush()
        return feedback
    
    async def get_urgent_feedback(
        self, clinic_id: UUID, limit: int = 10
    ) -> list[PatientFeedback]:
        """Acil işlem gereken geri bildirimleri al."""
        result = await self.db.execute(
            select(PatientFeedback).where(
                and_(
                    PatientFeedback.clinic_id == clinic_id,
                    PatientFeedback.requires_action == True,
                    PatientFeedback.is_resolved == False,
                )
            ).order_by(
                PatientFeedback.severity.desc(),
                PatientFeedback.created_at.asc(),
            ).limit(limit)
        )
        return result.scalars().all()
    
    async def get_overdue_feedback(
        self, clinic_id: UUID, hours: int = 24
    ) -> list[PatientFeedback]:
        """Yanıtlanmayan ve süresi geçmiş geri bildirimleri al."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(PatientFeedback).where(
                and_(
                    PatientFeedback.clinic_id == clinic_id,
                    PatientFeedback.is_resolved == False,
                    PatientFeedback.created_at < cutoff_time,
                )
            ).order_by(PatientFeedback.created_at.asc())
        )
        return result.scalars().all()


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP MESSAGE SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappMessageService:
    """WhatsApp mesaj gönderimi ve takibi."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def queue_message(
        self,
        clinic_id: UUID,
        data: WhatsappMessageCreate,
        idempotency_key: str,
    ) -> WhatsappMessageLog:
        """Mesajı kuyruğa al."""
        # Idempotency kontrolü
        result = await self.db.execute(
            select(WhatsappMessageLog).where(
                and_(
                    WhatsappMessageLog.clinic_id == clinic_id,
                    WhatsappMessageLog.idempotency_key == idempotency_key,
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"Message already queued: {idempotency_key}")
            return existing
        
        message = WhatsappMessageLog(
            clinic_id=clinic_id,
            idempotency_key=idempotency_key,
            status=WhatsappMessageStatus.QUEUED,
            **data.model_dump(),
        )
        self.db.add(message)
        await self.db.flush()
        
        logger.info(f"Message queued: {message.id} to {data.phone_number}")
        return message
    
    async def update_status(
        self,
        message_id: UUID,
        status: WhatsappMessageStatus,
        whatsapp_message_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> WhatsappMessageLog:
        """Mesaj durumunu güncelle."""
        result = await self.db.execute(
            select(WhatsappMessageLog).where(WhatsappMessageLog.id == message_id)
        )
        message = result.scalar_one_or_none()
        
        if not message:
            raise ValueError(f"Message not found: {message_id}")
        
        message.status = status
        if whatsapp_message_id:
            message.whatsapp_message_id = whatsapp_message_id
        if error_message:
            message.error_message = error_message
        message.updated_at = datetime.utcnow()
        
        await self.db.flush()
        
        logger.info(f"Message {message_id} status updated to {status}")
        return message
    
    async def get_failed_messages(
        self, clinic_id: UUID, limit: int = 100
    ) -> list[WhatsappMessageLog]:
        """Başarısız mesajları al (retry için)."""
        result = await self.db.execute(
            select(WhatsappMessageLog).where(
                and_(
                    WhatsappMessageLog.clinic_id == clinic_id,
                    WhatsappMessageLog.status == WhatsappMessageStatus.FAILED,
                    WhatsappMessageLog.retry_count < 3,
                )
            ).order_by(WhatsappMessageLog.created_at.asc()).limit(limit)
        )
        return result.scalars().all()
    
    async def increment_retry(self, message_id: UUID) -> WhatsappMessageLog:
        """Retry sayısını artır."""
        result = await self.db.execute(
            select(WhatsappMessageLog).where(WhatsappMessageLog.id == message_id)
        )
        message = result.scalar_one_or_none()
        
        if not message:
            raise ValueError(f"Message not found: {message_id}")
        
        message.retry_count += 1
        message.last_retry_at = datetime.utcnow()
        await self.db.flush()
        
        return message


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ClinicSettingsService",
    "DoctorSettingsService",
    "ClinicFaqService",
    "PatientFeedbackService",
    "WhatsappMessageService",
]
