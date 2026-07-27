"""
WhatsApp Entegrasyonu API Routers

REST endpoints:
- /api/clinic-settings
- /api/doctor-settings
- /api/clinic-faq
- /api/patient-feedback
- /api/whatsapp-messages
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_

from app.core.dependencies import get_db, get_current_user
from app.models.whatsapp import PatientFeedback
from app.schemas_whatsapp import (
    ClinicSettingsCreate,
    ClinicSettingsUpdate,
    ClinicSettingsResponse,
    DoctorSettingsCreate,
    DoctorSettingsUpdate,
    DoctorSettingsResponse,
    ClinicFaqCreate,
    ClinicFaqResponse,
    PatientFeedbackCreate,
    PatientFeedbackUpdate,
    PatientFeedbackResponse,
    PatientFeedbackListResponse,
    WhatsappMessageCreate,
    WhatsappMessageResponse,
    ErrorResponse,
)
from app.services.whatsapp_service import (
    ClinicSettingsService,
    DoctorSettingsService,
    ClinicFaqService,
    PatientFeedbackService,
    WhatsappMessageService,
)

router = APIRouter(prefix="/api", tags=["whatsapp"])


# ═══════════════════════════════════════════════════════════════════════════════
# CLINIC SETTINGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/clinic-settings",
    response_model=ClinicSettingsResponse,
    summary="Klinik ayarlarını al",
)
async def get_clinic_settings(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Klinik bildirim ve takip ayarlarını getir."""
    clinic_id = current_user.clinic_id
    service = ClinicSettingsService(db)
    settings = await service.get_or_create(clinic_id)
    return settings


@router.put(
    "/clinic-settings",
    response_model=ClinicSettingsResponse,
    summary="Klinik ayarlarını güncelle",
)
async def update_clinic_settings(
    data: ClinicSettingsUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Klinik ayarlarını güncelle."""
    clinic_id = current_user.clinic_id
    service = ClinicSettingsService(db)
    settings = await service.update(clinic_id, data)
    await db.commit()
    return settings


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR SETTINGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/doctor-settings",
    response_model=DoctorSettingsResponse,
    summary="Doktor ayarlarını al",
)
async def get_doctor_settings(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Doktor bildirim ve AI ayarlarını getir."""
    clinic_id = current_user.clinic_id
    doctor_id = current_user.id
    
    service = DoctorSettingsService(db)
    settings = await service.get_or_create(clinic_id, doctor_id)
    return settings


@router.put(
    "/doctor-settings",
    response_model=DoctorSettingsResponse,
    summary="Doktor ayarlarını güncelle",
)
async def update_doctor_settings(
    data: DoctorSettingsUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Doktor ayarlarını güncelle."""
    clinic_id = current_user.clinic_id
    doctor_id = current_user.id
    
    service = DoctorSettingsService(db)
    settings = await service.update(clinic_id, doctor_id, data)
    await db.commit()
    return settings


# ═══════════════════════════════════════════════════════════════════════════════
# CLINIC FAQ ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/clinic-faq",
    response_model=ClinicFaqResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni SSS oluştur",
)
async def create_faq(
    data: ClinicFaqCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Klinik SSS'i oluştur."""
    clinic_id = current_user.clinic_id
    service = ClinicFaqService(db)
    
    faq = await service.create(clinic_id, data, current_user.id)
    await db.commit()
    return faq


@router.get(
    "/clinic-faq/by-category/{category}",
    response_model=list[ClinicFaqResponse],
    summary="Kategoriye göre SSS'leri al",
)
async def get_faq_by_category(
    category: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kategoriye göre yayınlanmış SSS'leri getir."""
    clinic_id = current_user.clinic_id
    service = ClinicFaqService(db)
    
    faqs = await service.get_published_by_category(clinic_id, category)
    return faqs


@router.get(
    "/clinic-faq",
    response_model=list[ClinicFaqResponse],
    summary="Tüm SSS'leri listele",
)
async def list_all_faq(
    status: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tüm SSS'leri listele (filtreleme opsiyonel)."""
    from sqlalchemy import select, and_
    from app.models.whatsapp import ClinicFaq
    
    clinic_id = current_user.clinic_id
    query = select(ClinicFaq).where(ClinicFaq.clinic_id == clinic_id)
    
    if status:
        query = query.where(ClinicFaq.status == status)
    if category:
        query = query.where(ClinicFaq.category == category)
    
    query = query.order_by(ClinicFaq.priority.asc(), ClinicFaq.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    faqs = result.scalars().all()
    return faqs


@router.get(
    "/clinic-faq/{faq_id}",
    response_model=ClinicFaqResponse,
    summary="SSS detaylarını al",
)
async def get_faq_by_id(
    faq_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSS'nin detaylı bilgisini getir."""
    from sqlalchemy import select
    from app.models.whatsapp import ClinicFaq
    
    result = await db.execute(
        select(ClinicFaq).where(
            and_(
                ClinicFaq.id == faq_id,
                ClinicFaq.clinic_id == current_user.clinic_id,
            )
        )
    )
    faq = result.scalar_one_or_none()
    
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found",
        )
    
    return faq


@router.put(
    "/clinic-faq/{faq_id}",
    response_model=ClinicFaqResponse,
    summary="SSS'yi güncelle",
)
async def update_faq(
    faq_id: UUID,
    data: ClinicFaqCreate,  # Reuse create schema as update
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSS'yi güncelle."""
    from sqlalchemy import select
    from app.models.whatsapp import ClinicFaq
    from datetime import datetime
    
    result = await db.execute(
        select(ClinicFaq).where(
            and_(
                ClinicFaq.id == faq_id,
                ClinicFaq.clinic_id == current_user.clinic_id,
            )
        )
    )
    faq = result.scalar_one_or_none()
    
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found",
        )
    
    # Update fields
    faq.question = data.question
    faq.answer = data.answer
    faq.category = data.category
    faq.priority = data.priority
    faq.video_url = data.video_url
    faq.attachment_urls = data.attachment_urls or []
    faq.whatsapp_template_key = data.whatsapp_template_key
    faq.status = data.status
    faq.updated_at = datetime.utcnow()
    
    db.add(faq)
    await db.flush()
    
    return faq


@router.delete(
    "/clinic-faq/{faq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="SSS'yi sil",
)
async def delete_faq(
    faq_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSS'yi sil (soft delete)."""
    from sqlalchemy import select
    from app.models.whatsapp import ClinicFaq
    
    result = await db.execute(
        select(ClinicFaq).where(
            and_(
                ClinicFaq.id == faq_id,
                ClinicFaq.clinic_id == current_user.clinic_id,
            )
        )
    )
    faq = result.scalar_one_or_none()
    
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found",
        )
    
    faq.status = "archived"
    db.add(faq)
    await db.flush()


@router.post(
    "/clinic-faq/search",
    response_model=list[ClinicFaqResponse],
    summary="SSS'lerde arama yap",
)
async def search_faq(
    keywords: str,
    limit: int = 5,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Anahtar kelimelerle SSS'lerde ara (RAG için)."""
    clinic_id = current_user.clinic_id
    service = ClinicFaqService(db)
    
    faqs = await service.search_by_keywords(clinic_id, keywords, limit)
    return faqs


# ═══════════════════════════════════════════════════════════════════════════════
# PATIENT FEEDBACK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/patient-feedback",
    response_model=PatientFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni hasta geri bildirimi oluştur",
)
async def create_feedback(
    data: PatientFeedbackCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yeni hasta geri bildirimi oluştur."""
    clinic_id = current_user.clinic_id
    service = PatientFeedbackService(db)
    
    feedback = await service.create(clinic_id, data)
    await db.commit()
    return feedback


@router.get(
    "/patient-feedback/{feedback_id}",
    response_model=PatientFeedbackResponse,
    summary="Hasta geri bildirimi al",
)
async def get_feedback(
    feedback_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hasta geri bildirimi detaylarını getir."""
    # NOTE: Gerçek implementasyonda RLS kontrol etmeli
    from sqlalchemy import select
    result = await db.execute(
        select(PatientFeedback).where(PatientFeedback.id == feedback_id)
    )
    feedback = result.scalar_one_or_none()
    
    if not feedback or feedback.clinic_id != current_user.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    
    return feedback


@router.put(
    "/patient-feedback/{feedback_id}",
    response_model=PatientFeedbackResponse,
    summary="Hasta geri bildirimi güncelle",
)
async def update_feedback(
    feedback_id: UUID,
    data: PatientFeedbackUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hasta geri bildirimi güncelle."""
    service = PatientFeedbackService(db)
    
    feedback = await service.update(feedback_id, data)
    await db.commit()
    return feedback


@router.get(
    "/patient-feedback/urgent",
    response_model=list[PatientFeedbackResponse],
    summary="Acil geri bildirimleri al",
)
async def get_urgent_feedback(
    limit: int = 10,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Acil işlem gereken geri bildirimleri getir."""
    clinic_id = current_user.clinic_id
    service = PatientFeedbackService(db)
    
    feedbacks = await service.get_urgent_feedback(clinic_id, limit)
    return feedbacks


@router.get(
    "/patient-feedback/overdue",
    response_model=list[PatientFeedbackResponse],
    summary="Süresi geçmiş geri bildirimleri al",
)
async def get_overdue_feedback(
    hours: int = 24,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yanıtlanmayan ve süresi geçmiş geri bildirimleri getir."""
    clinic_id = current_user.clinic_id
    service = PatientFeedbackService(db)
    
    feedbacks = await service.get_overdue_feedback(clinic_id, hours)
    return feedbacks


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP MESSAGE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/whatsapp-messages/send",
    response_model=WhatsappMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="WhatsApp mesajı gönder",
)
async def send_whatsapp_message(
    data: WhatsappMessageCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """WhatsApp mesajı kuyruğa al."""
    clinic_id = current_user.clinic_id
    service = WhatsappMessageService(db)
    
    # Idempotency key: clinic_id + phone + message_type + timestamp
    import hashlib
    from datetime import datetime
    key_data = f"{clinic_id}:{data.phone_number}:{data.message_type}:{datetime.utcnow().isoformat()}"
    idempotency_key = hashlib.sha256(key_data.encode()).hexdigest()
    
    message = await service.queue_message(clinic_id, data, idempotency_key)
    await db.commit()
    return message


@router.get(
    "/whatsapp-messages/{message_id}",
    response_model=WhatsappMessageResponse,
    summary="WhatsApp mesaj durumu al",
)
async def get_whatsapp_message(
    message_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """WhatsApp mesaj durumunu getir."""
    from app.models.whatsapp import WhatsappMessageLog
    from sqlalchemy import select
    
    result = await db.execute(
        select(WhatsappMessageLog).where(WhatsappMessageLog.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message or message.clinic_id != current_user.clinic_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    return message


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/health/whatsapp",
    summary="WhatsApp entegrasyon sağlığını kontrol et",
)
async def whatsapp_health(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """WhatsApp entegrasyon durumunu kontrol et."""
    from app.services.whatsapp_service import ClinicSettingsService
    
    service = ClinicSettingsService(db)
    settings = await service.get_or_create(current_user.clinic_id)
    
    return {
        "status": "healthy" if settings.is_whatsapp_enabled else "disabled",
        "whatsapp_enabled": settings.is_whatsapp_enabled,
        "clinic_id": current_user.clinic_id,
    }


__all__ = ["router"]
