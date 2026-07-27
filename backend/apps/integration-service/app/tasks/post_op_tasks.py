"""
Post-Appointment Follow-up Tasks

Tedavi sonrası hasta takip mekanizması:
- Tamamlanan tedavilerin takip zamanlarını kontrolü
- AI tarafından hasta mesajlaşması
- Hasta geri bildirimi alınması
- RAG motoru ile SSS merkezli yanıtlama
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timedelta
from uuid import UUID

from celery import shared_task
from sqlalchemy import select, and_, text

from app.celery_app import app
from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.models.whatsapp import (
    ClinicSettings,
    DoctorSettings,
    PatientFeedback,
    WhatsappMessageLog,
)
try:
    from app.models import Appointment, Clinic, Patient
except ImportError:
    # Integration service only defines WhatsApp extension models locally.
    # Fallback keeps module importable for API startup; manual task uses SQL.
    Appointment = Clinic = Patient = None
from app.providers.whatsapp_provider import get_whatsapp_provider
from app.services.whatsapp_service import WhatsappMessageService
from app.services.rag_service import RAGService
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


def _resolve_postop_due_at(
    scheduled_at: datetime,
    intervals: object | None,
) -> datetime | None:
    if isinstance(intervals, dict):
        if not intervals.get("enabled", True):
            return None
        return scheduled_at + timedelta(days=int(intervals.get("interval_days", 1)))

    if isinstance(intervals, list):
        enabled_offsets: list[timedelta] = []
        for entry in intervals:
            if not isinstance(entry, dict) or not entry.get("enabled", True):
                continue
            if entry.get("hours_after") is not None:
                enabled_offsets.append(timedelta(hours=int(entry["hours_after"])))
                continue
            if entry.get("days_after") is not None:
                enabled_offsets.append(timedelta(days=int(entry["days_after"])))

        if not enabled_offsets:
            return None

        return scheduled_at + min(enabled_offsets)

    return None


@app.task(
    bind=True,
    name="post_op_tasks.send_postop_followup_messages",
    queue="appointments",
    max_retries=5,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def send_postop_followup_messages(self):
    """
    Periyodik task: Tamamlanan tedavilerin takip zamanları gelmişse,
    hastaya AI tarafından takip mesajı gönder.

    Tetikleyici: Celery Beat (saatlik)
    """
    try:
        return asyncio.run(_send_postop_followup_impl())
    except Exception as exc:
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    name="post_op_tasks.send_postop_followup_for_appointment",
    queue="appointments",
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def send_postop_followup_for_appointment(
    self,
    clinic_id: str,
    appointment_id: str,
):
    """
    Manuel tetikleme: Belirli bir completed randevu için hemen post-op takip mesajı gönder.
    """
    try:
        return asyncio.run(_send_single_postop_impl(clinic_id, appointment_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _send_single_postop_impl(clinic_id: str, appointment_id: str):
    async with AsyncSessionFactory() as db:
        appt = (
            await db.execute(
                text(
                    """
                    SELECT
                        a.id,
                        a.clinic_id,
                        a.status,
                        a.scheduled_at,
                        a.treatment_follow_up_enabled,
                        p.full_name AS patient_name,
                        p.phone AS patient_phone,
                        c.name AS clinic_name,
                        c.settings AS clinic_settings,
                        COALESCE(d.full_name, 'Doktor') AS doctor_name
                    FROM appointments a
                    JOIN patients p ON p.id = a.patient_id AND p.clinic_id = a.clinic_id
                    JOIN clinics c ON c.id = a.clinic_id
                    LEFT JOIN doctors d ON d.id = a.doctor_id AND d.clinic_id = a.clinic_id
                    WHERE a.id = :appointment_id
                      AND a.clinic_id = :clinic_id
                    LIMIT 1
                    """
                ),
                {"appointment_id": appointment_id, "clinic_id": clinic_id},
            )
        ).mappings().first()

        if not appt:
            return {"status": "failed", "reason": "appointment_not_found"}

        if appt["status"] != "completed":
            return {"status": "skipped", "reason": "appointment_not_completed"}

        if not appt["treatment_follow_up_enabled"]:
            return {"status": "skipped", "reason": "treatment_followup_disabled"}

        clinic_result = await db.execute(
            select(ClinicSettings).where(ClinicSettings.clinic_id == appt["clinic_id"])
        )
        clinic_settings = clinic_result.scalar_one_or_none()
        if not clinic_settings or not clinic_settings.is_whatsapp_enabled:
            return {"status": "skipped", "reason": "whatsapp_disabled"}

        msg_check = await db.execute(
            select(WhatsappMessageLog).where(
                and_(
                    WhatsappMessageLog.clinic_id == appt["clinic_id"],
                    WhatsappMessageLog.phone_number == appt["patient_phone"],
                    WhatsappMessageLog.message_type == "post_op_followup",
                    WhatsappMessageLog.template_variables["appointment_id"] == str(appt["id"]),
                )
            )
        )
        if msg_check.scalar_one_or_none():
            return {"status": "skipped", "reason": "already_sent"}

        doctor_name = appt["doctor_name"] or "Doktor"
        appointment_date_str = appt["scheduled_at"].strftime("%d.%m.%Y %H:%M")
        clinic_settings_json = appt.get("clinic_settings") if isinstance(appt, dict) else None
        language = (
            clinic_settings_json.get("language", "tr")
            if isinstance(clinic_settings_json, dict)
            else "tr"
        )

        try:
            llm = get_llm_service()
            message_text = await llm.generate_appointment_confirmation_message(
                patient_name=appt["patient_name"],
                doctor_name=doctor_name,
                appointment_date=appointment_date_str,
                appointment_time="",
                clinic_name=appt["clinic_name"],
                language=language,
            )
            message_text = (
                f"{message_text}\n\n"
                "Tedavi sonrası bir şikayetiniz var mı? "
                "Varsa lütfen yazın, size yardımcı olalım."
            )
        except Exception:
            message_text = (
                f"Merhaba {appt['patient_name']}! 👋\n\n"
                "Tedavi sonrası nasılsınız? Şikayetiniz (ağrı/şişlik/kanama/hassasiyet) "
                "varsa bize yazabilirsiniz."
            )

        provider = get_whatsapp_provider(clinic_settings)
        await provider.send_text_message(phone_number=appt["patient_phone"], text=message_text)

        msg_service = WhatsappMessageService(db)
        from app.schemas_whatsapp import WhatsappMessageCreate

        idempotency_key = (
            f"{appt['clinic_id']}:{appt['patient_phone']}:post_op_followup:{appt['id']}:manual"
        )
        msg = WhatsappMessageCreate(
            phone_number=appt["patient_phone"],
            message_type="post_op_followup",
            template_key="post_op_followup",
            template_variables={
                "patient_name": appt["patient_name"],
                "doctor_name": doctor_name,
                "appointment_id": str(appt["id"]),
                "appointment_date": appointment_date_str,
                "manual": True,
            },
        )
        await msg_service.queue_message(appt["clinic_id"], msg, idempotency_key)
        await db.commit()
        return {"status": "sent", "appointment_id": appointment_id}


async def _send_postop_followup_impl():
    async with AsyncSessionFactory() as db:
        try:
            logger.info("[POST_OP] Sending post-op follow-up messages...")
            stats = {
                "checked": 0,
                "sent": 0,
                "failed": 0,
                "skipped": 0,
            }

            # Only look at appointments completed in the last 7 days to avoid
            # loading the entire history into memory on every run.
            cutoff = datetime.utcnow() - timedelta(days=7)
            result = await db.execute(
                text(
                    """
                    SELECT
                        a.id,
                        a.clinic_id,
                        a.patient_id,
                        a.scheduled_at,
                        a.treatment_follow_up_enabled,
                        p.full_name AS patient_name,
                        p.phone AS patient_phone,
                        c.name AS clinic_name,
                        COALESCE(d.full_name, 'Doktor') AS doctor_name
                    FROM appointments a
                    JOIN patients p ON p.id = a.patient_id AND p.clinic_id = a.clinic_id
                    JOIN clinics c ON c.id = a.clinic_id
                    LEFT JOIN doctors d ON d.id = a.doctor_id AND d.clinic_id = a.clinic_id
                    WHERE a.status = 'completed'
                      AND a.scheduled_at >= :cutoff
                      AND COALESCE(a.treatment_follow_up_enabled, FALSE) = TRUE
                    ORDER BY a.scheduled_at DESC
                    LIMIT 500
                    """
                ),
                {"cutoff": cutoff},
            )
            completed_appointments = result.mappings().all()
            stats["checked"] = len(completed_appointments)

            for appt in completed_appointments:
                try:
                    if not appt["patient_phone"]:
                        logger.warning(
                            "[POST_OP] Appointment %s has no patient phone",
                            appt["id"],
                        )
                        stats["skipped"] += 1
                        continue

                    # Clinic settings kontrol et
                    clinic_result = await db.execute(
                        select(ClinicSettings).where(
                            ClinicSettings.clinic_id == appt["clinic_id"]
                        )
                    )
                    clinic_settings = clinic_result.scalar_one_or_none()

                    if (
                        not clinic_settings
                        or not clinic_settings.is_whatsapp_enabled
                        or not clinic_settings.post_op_followup_intervals
                    ):
                        stats["skipped"] += 1
                        continue

                    followup_due_at = _resolve_postop_due_at(
                        appt["scheduled_at"],
                        clinic_settings.post_op_followup_intervals,
                    )

                    if followup_due_at is None or datetime.utcnow() < followup_due_at:
                        stats["skipped"] += 1
                        continue

                    # Bu appointment için zaten takip mesajı gönderildi mi? Kontrol et
                    msg_check = await db.execute(
                        select(WhatsappMessageLog).where(
                            and_(
                                WhatsappMessageLog.clinic_id == appt["clinic_id"],
                                WhatsappMessageLog.phone_number
                                == appt["patient_phone"],
                                WhatsappMessageLog.message_type == "post_op_followup",
                                WhatsappMessageLog.template_variables["appointment_id"]
                                == str(appt["id"]),
                            )
                        )
                    )
                    if msg_check.scalar_one_or_none():
                        stats["skipped"] += 1
                        continue

                    # === MESAJ GÖNDER ===
                    doctor_name = appt["doctor_name"] or "Doktor"
                    appointment_date_str = appt["scheduled_at"].strftime(
                        "%d.%m.%Y %H:%M"
                    )

                    # Try AI-personalized message; fall back to static template
                    try:
                        llm = get_llm_service()
                        message_text = await llm.generate_appointment_confirmation_message(
                            patient_name=appt["patient_name"],
                            doctor_name=doctor_name,
                            appointment_date=appointment_date_str,
                            appointment_time="",
                            clinic_name=appt["clinic_name"],
                            language=clinic_settings.whatsapp_template_lang or "tr",
                        )
                        # Personalise for post-op context (append complaint prompt)
                        message_text = (
                            f"{message_text}\n\n"
                            "Tedavi sonrası bir şikayetiniz var mı? "
                            "Varsa lütfen yazın, size yardımcı olalım."
                        )
                    except Exception as ai_err:
                        logger.warning("[POST_OP] LLM unavailable, using static message: %s", ai_err)
                        message_text = (
                            f"Merhaba {appt['patient_name']}! 👋\n\n"
                            f"{appointment_date_str} gününde {doctor_name} hocamızda "
                            f"tedavi oldunuz. Hocamız nasıl olduğunuzu sormamı istedi.\n\n"
                            f"Bir şikayetiniz var mı? Örneğin:\n"
                            f"- Ağrı\n- Şişme\n- Kanamalar\n- Diş hassasiyeti\n\n"
                            f"Lütfen şikayetinizi yazın (varsa)."
                        )

                    # WhatsApp provider ile mesaj gönder
                    provider = get_whatsapp_provider(clinic_settings)
                    idempotency_key = f"{appt['clinic_id']}:{appt['patient_phone']}:post_op_followup:{appt['id']}"

                    try:
                        await provider.send_text_message(
                            phone_number=appt["patient_phone"],
                            text=message_text,
                        )

                        # Log message
                        msg_service = WhatsappMessageService(db)
                        from app.schemas_whatsapp import WhatsappMessageCreate

                        msg = WhatsappMessageCreate(
                            phone_number=appt["patient_phone"],
                            message_type="post_op_followup",
                            template_key="post_op_followup",
                            template_variables={
                                "patient_name": appt["patient_name"],
                                "doctor_name": doctor_name,
                                "appointment_id": str(appt["id"]),
                                "appointment_date": appointment_date_str,
                            },
                        )
                        await msg_service.queue_message(
                            appt["clinic_id"], msg, idempotency_key
                        )
                        await db.commit()

                        stats["sent"] += 1
                        logger.info(
                            f"[POST_OP] Sent follow-up to {appt['patient_phone']} "
                            f"(appointment {appt['id']})"
                        )

                    except Exception as e:
                        stats["failed"] += 1
                        logger.error(
                            f"[POST_OP] Failed to send message to {patient.phone_number}: {e}"
                        )

                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"[POST_OP] Error processing appointment {appt.id}: {e}")
                    continue

            logger.info(f"[POST_OP] Task completed. Stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"[POST_OP] Task failed: {e}")
            raise


@app.task(
    bind=True,
    name="post_op_tasks.process_patient_feedback_response",
    queue="ai",
    max_retries=5,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def process_patient_feedback_response(
    self,
    clinic_id: str,
    patient_id: str,
    patient_message: str,
    appointment_id: str | None = None,
):
    """
    Celery task: Hasta geri bildirimi mesajını işle.

    1. RAG motoru ile ClinicFAQ'lardan relevant SSS'leri çek
    2. AI LLM'ini kullanarak severity sınıflandırması yap
    3. PatientFeedback tablosuna kaydı yap
    4. Doktor uyarısı gerekiyorsa WhatsApp gönder
    """
    try:
        return asyncio.run(
            _process_feedback_impl(clinic_id, patient_id, patient_message, appointment_id)
        )
    except Exception as exc:
        raise self.retry(exc=exc)


async def _process_feedback_impl(
    clinic_id: str,
    patient_id: str,
    patient_message: str,
    appointment_id: str | None,
):
    async with AsyncSessionFactory() as db:
        try:
            logger.info(
                f"[FEEDBACK] Processing feedback from patient {patient_id}: {patient_message[:50]}..."
            )

            clinic_id = UUID(clinic_id) if isinstance(clinic_id, str) else clinic_id
            patient_id = UUID(patient_id) if isinstance(patient_id, str) else patient_id
            appointment_id = (
                UUID(appointment_id) if isinstance(appointment_id, str) else appointment_id
            )

            # Patient ve Clinic bilgisi al
            patient = await db.get(Patient, patient_id)
            clinic = await db.get(Clinic, clinic_id)
            clinic_settings_result = await db.execute(
                select(ClinicSettings).where(ClinicSettings.clinic_id == clinic_id)
            )
            clinic_settings = clinic_settings_result.scalar_one_or_none()

            if not patient or not clinic:
                logger.warning(
                    f"[FEEDBACK] Patient {patient_id} or clinic {clinic_id} not found"
                )
                return {"status": "failed", "reason": "patient_not_found"}

            # === RAG: RELEVANT FAQ'LAR ===
            rag_service = RAGService(db)
            faqs = await rag_service.search_relevant_faqs(clinic_id, patient_message, limit=3)

            # === AI: SEVERITY SINIFLANDIRMASI ===
            from app.services.llm_service import get_llm_service

            llm_service = get_llm_service()
            severity_result = await llm_service.classify_feedback_severity(
                feedback_message=patient_message,
                feedback_type="post_appointment_followup",
                context=f"Klinik: {clinic.name}. Hasta: {patient.full_name}. Tedavi türü: {appointment_id}",
                language=clinic.metadata.get("language", "tr") if clinic.metadata else "tr",
            )

            severity = severity_result.get("severity", "medium")
            requires_action = severity_result.get("requires_immediate_action", False)
            suggested_action = severity_result.get("suggested_action", "")
            confidence = severity_result.get("confidence", 0.5)

            logger.info(
                f"[FEEDBACK] Classified severity: {severity} (confidence: {confidence})"
            )

            # === PatientFeedback KAYDI ===
            feedback_obj = PatientFeedback(
                clinic_id=clinic_id,
                patient_id=patient_id,
                appointment_id=appointment_id,
                feedback_type="post_appointment_followup",
                severity=severity,
                message=patient_message,
                requires_action=requires_action or severity in ["high", "critical"],
                assigned_to_user_id=None,  # TODO: Auto-assign to treating doctor
                channel="whatsapp",
                image_urls=[],
                is_resolved=False,
            )
            db.add(feedback_obj)
            await db.flush()

            # === DOKTOR UYARISI (gerekiyorsa) ===
            if requires_action or severity in ["high", "critical"]:
                appointment = (
                    await db.get(Appointment, appointment_id)
                    if appointment_id
                    else None
                )
                doctor_name = appointment.doctor_name if appointment else "Doktor"
                appointment_date = (
                    appointment.appointment_date.strftime("%d.%m.%Y")
                    if appointment
                    else "N/A"
                )

                # Doctor settings kontrol et
                doctor_result = await db.execute(
                    select(DoctorSettings).where(
                        and_(
                            DoctorSettings.clinic_id == clinic_id,
                            DoctorSettings.receive_emergency_alerts == True,
                        )
                    )
                )
                doctors = doctor_result.scalars().all()

                if doctors:
                    # Alert message oluştur
                    alert_msg = rag_service.build_doctor_alert_message(
                        patient_name=patient.full_name,
                        patient_message=patient_message,
                        appointment_date=appointment_date,
                        doctor_name=doctor_name,
                        severity=severity,
                        faqs=faqs,
                    )

                    # Her doktora mesaj gönder
                    provider = get_whatsapp_provider(clinic_settings)
                    for doctor in doctors:
                        try:
                            # Doktor kişisel WhatsApp numarası (TODO: doctor profile'da tutulmalı)
                            doctor_phone = (
                                doctor.metadata.get("whatsapp_phone")
                                if doctor.metadata
                                else None
                            )
                            if doctor_phone:
                                await provider.send_text_message(
                                    phone_number=doctor_phone,
                                    text=alert_msg,
                                )
                                logger.info(
                                    f"[FEEDBACK] Sent alert to doctor {doctor.doctor_id}"
                                )
                        except Exception as e:
                            logger.error(
                                f"[FEEDBACK] Failed to alert doctor {doctor.doctor_id}: {e}"
                            )

            await db.commit()

            logger.info(
                f"[FEEDBACK] Successfully processed feedback from {patient.full_name} "
                f"(severity: {severity})"
            )
            return {
                "status": "success",
                "feedback_id": str(feedback_obj.id),
                "severity": severity,
                "faq_count": len(faqs),
            }

        except Exception as e:
            logger.error(f"[FEEDBACK] Task failed: {e}")
            raise


@app.task(
    bind=True,
    name="post_op_tasks.send_faq_response_to_patient",
    queue="ai",
    max_retries=2,
    autoretry_for=(Exception,),
    default_retry_delay=60,
)
async def send_faq_response_to_patient(
    self,
    clinic_id: str,
    patient_phone: str,
    patient_message: str,
    feedback_id: str,
):
    """
    Celery task: Hastaya RAG temelli FAQ yanıt gönder.
    
    1. RAG motoru ile relevant FAQ'ları bul
    2. AI prompt'una FAQ context'i enjekte et
    3. Hastaya klinik onaylı yanıt mesajı gönder
    
    Args:
        clinic_id: Klinik ID
        patient_phone: Hasta phone numarası
        patient_message: Hastanın orijinal mesajı
        feedback_id: PatientFeedback record ID
    """
    async with AsyncSessionFactory() as db:
        try:
            logger.info(
                f"[FAQ_RESPONSE] Sending FAQ-based response to {patient_phone}: "
                f"{patient_message[:50]}..."
            )

            clinic_id = UUID(clinic_id) if isinstance(clinic_id, str) else clinic_id

            clinic = await db.get(Clinic, clinic_id)
            if not clinic:
                logger.warning(f"[FAQ_RESPONSE] Clinic {clinic_id} not found")
                return {"status": "failed", "reason": "clinic_not_found"}

            # === RAG: RELEVANT FAQ'LAR ===
            rag_service = RAGService(db)
            faqs = await rag_service.search_relevant_faqs(
                clinic_id, patient_message, limit=3
            )

            if not faqs:
                # FAQ bulunamadı, doktora yönlendir
                fallback_message = (
                    f"Üzgünüz, bu konuda hemen yardımcı olamıyorum. "
                    f"Lütfen {clinic.name} ile doğrudan iletişime geçin. "
                    f"Hekiminiz sizle en kısa sürede temasa geçecektir."
                )
                await _send_whatsapp_message(patient_phone, fallback_message, clinic_settings)
                logger.info(
                    f"[FAQ_RESPONSE] No FAQs found for message, sent fallback to {patient_phone}"
                )
                return {"status": "no_faq", "message": "Fallback sent"}

            # === AI: Severity sınıflandır ve kişiselleştirilmiş yanıt oluştur ===
            llm_service = get_llm_service()

            try:
                severity_result = await llm_service.classify_feedback_severity(
                    feedback_message=patient_message,
                    feedback_type="post_treatment_complaint",
                    context=f"Klinik: {clinic.name}",
                    language=clinic.metadata.get("language", "tr") if clinic.metadata else "tr",
                )
                severity = severity_result.get("severity", "medium")
            except Exception:
                severity = "medium"

            try:
                faq_dicts = [
                    {"question": f.question, "answer": f.answer}
                    for f in faqs
                ]
                response_message = await llm_service.generate_feedback_solution_message(
                    patient_name="",   # phone-only context, name not passed here
                    patient_complaint=patient_message,
                    severity=severity,
                    faqs=faq_dicts,
                    clinic_name=clinic.name,
                    language=clinic.metadata.get("language", "tr") if clinic.metadata else "tr",
                )
            except Exception as ai_err:
                logger.warning("[FAQ_RESPONSE] LLM failed, falling back to FAQ list: %s", ai_err)
                response_message = "Bulduğum ilgili bilgiler:\n\n"
                for i, faq in enumerate(faqs, 1):
                    response_message += f"{i}. {faq.question}\n→ {faq.answer}\n\n"
                response_message += "\nEğer sorunuz devam ederse lütfen doktorunuzla iletişime geçin."

            await _send_whatsapp_message(patient_phone, response_message, clinic_settings)

            logger.info(f"[FAQ_RESPONSE] Sent AI-powered solution response to {patient_phone}")
            return {
                "status": "success",
                "faq_count": len(faqs),
                "severity": severity,
                "feedback_id": feedback_id,
            }

        except Exception as e:
            logger.error(f"[FAQ_RESPONSE] Task failed: {e}")
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


async def _send_whatsapp_message(
    phone_number: str,
    text: str,
    clinic_settings: ClinicSettings | None = None,
) -> bool:
    """Helper: WhatsApp mesajı gönder."""
    try:
        provider = get_whatsapp_provider(clinic_settings)
        await provider.send_text_message(phone_number, text)
        return True
    except Exception as e:
        logger.error(f"[HELPER] Failed to send message to {phone_number}: {e}")
        return False
