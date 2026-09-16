"""
DentAI Flow Monolith — Event Bus Uyumluluk Katmanı
====================================================
Eski mikroservis yapısında:
    appointment-service → RabbitMQ publish → notification-service consumer

Monolith'te:
    publish_event() → doğrudan APScheduler job veya async fonksiyon çağrısı

Bu modül eski `from app.core.broker import publish_event` import'larını
kırmadan event'leri doğrudan işler.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def publish_event(routing_key: str, payload: dict[str, Any]) -> None:
    """
    Eski: RabbitMQ'ya mesaj publish et.
    Yeni: Event'e göre APScheduler job veya doğrudan async çağrı.

    Desteklenen routing key'ler:
        appointment.confirmed   → WhatsApp hatırlatma zamanla
        appointment.completed   → Post-op takip zamanla
        appointment.cancelled   → Hatırlatma iptal et
        waitlist.match_found    → Yedek hasta bildir
    """
    logger.debug(f"Event: {routing_key} | payload keys: {list(payload.keys())}")

    try:
        if routing_key == "appointment.confirmed":
            await _handle_appointment_confirmed(payload)
        elif routing_key == "appointment.completed":
            await _handle_appointment_completed(payload)
        elif routing_key == "appointment.cancelled":
            await _handle_appointment_cancelled(payload)
        elif routing_key == "waitlist.match_found":
            await _handle_waitlist_match_found(payload)
        else:
            logger.warning(f"Bilinmeyen event routing key: {routing_key}")
    except Exception as e:
        # Event işleme hatası ana iş akışını kesmemeli
        logger.error(f"Event işleme hatası ({routing_key}): {e}")


async def _handle_appointment_confirmed(payload: dict[str, Any]) -> None:
    """Randevu teyit edildi → WhatsApp hatırlatma zamanla."""
    from datetime import datetime
    from uuid import UUID
    from app.core.scheduler import schedule_whatsapp_reminder

    appointment_id = payload.get("appointment_id")
    clinic_id = payload.get("clinic_id")
    scheduled_at_str = payload.get("scheduled_at")

    if not all([appointment_id, clinic_id, scheduled_at_str]):
        return

    scheduled_at = datetime.fromisoformat(scheduled_at_str)

    # Hasta telefon numarasını DB'den almak için lazy import
    try:
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            await db.execute(
                text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(clinic_id))
            )
            result = await db.execute(
                text("""
                    SELECT p.phone, p.full_name
                    FROM appointments a
                    JOIN patients p ON p.id = a.patient_id
                    WHERE a.id = :aid
                """),
                {"aid": str(appointment_id)},
            )
            row = result.mappings().first()
            if row:
                schedule_whatsapp_reminder(
                    appointment_id=UUID(appointment_id),
                    clinic_id=UUID(clinic_id),
                    patient_phone=row["phone"] or "",
                    patient_name=row["full_name"] or "",
                    appointment_time=scheduled_at,
                )
    except Exception as e:
        logger.error(f"Hatırlatma zamanlanamadı: {e}")


async def _handle_appointment_completed(payload: dict[str, Any]) -> None:
    """Randevu tamamlandı → Post-op takip hemen kuyruğa al."""
    clinic_id = payload.get("clinic_id")
    appointment_id = payload.get("appointment_id")
    if not clinic_id or not appointment_id:
        logger.warning("appointment.completed eksik payload: %s", payload)
        return

    from app.tasks.post_op_tasks import send_postop_followup_for_appointment

    send_postop_followup_for_appointment.delay(str(clinic_id), str(appointment_id))
    logger.info(
        "Post-op follow-up kuyruğa alındı: clinic=%s appointment=%s",
        clinic_id,
        appointment_id,
    )


async def _handle_appointment_cancelled(payload: dict[str, Any]) -> None:
    """Randevu iptal edildi → Zamanlanmış hatırlatmayı iptal et."""
    from uuid import UUID
    from app.core.scheduler import cancel_whatsapp_reminder

    appointment_id = payload.get("appointment_id")
    if appointment_id:
        cancel_whatsapp_reminder(UUID(appointment_id))
        logger.info(f"İptal sonrası hatırlatma kaldırıldı: {appointment_id}")


async def _handle_waitlist_match_found(payload: dict[str, Any]) -> None:
    """Yedek eşleşmesi bulundu → mümkünse WhatsApp bildirimi gönder."""
    clinic_id = payload.get("clinic_id")
    patient_id = payload.get("patient_id")
    specialty = payload.get("specialty")
    logger.info(
        "Yedek eşleşme: patient_id=%s specialty=%s clinic_id=%s",
        patient_id,
        specialty,
        clinic_id,
    )

    if not clinic_id or not patient_id:
        return

    try:
        from sqlalchemy import text

        from app.core.database import AsyncSessionLocal
        from app.models.whatsapp import ClinicSettings
        from app.providers.whatsapp_provider import get_whatsapp_provider
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            await db.execute(
                text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(
                    cid=str(clinic_id)
                )
            )
            patient = (
                await db.execute(
                    text(
                        """
                        SELECT full_name, phone
                        FROM patients
                        WHERE id = :pid AND clinic_id = :cid
                        LIMIT 1
                        """
                    ),
                    {"pid": str(patient_id), "cid": str(clinic_id)},
                )
            ).mappings().first()
            if not patient or not patient.get("phone"):
                logger.info("Waitlist match: hasta telefonu yok, bildirim atlandı")
                return

            settings = (
                await db.execute(
                    select(ClinicSettings).where(ClinicSettings.clinic_id == clinic_id)
                )
            ).scalar_one_or_none()
            if not settings or not settings.is_whatsapp_enabled:
                logger.info("Waitlist match: WhatsApp kapalı, bildirim atlandı")
                return

            provider = get_whatsapp_provider(settings)
            name = patient.get("full_name") or "Hastamız"
            branch = specialty or "ilgili branş"
            text_msg = (
                f"Merhaba {name}, {branch} için uygun bir randevu boşluğu oluştu. "
                f"Klinik sizinle iletişime geçebilir — lütfen telefonunuzu açık tutun."
            )
            await provider.send_text_message(phone_number=patient["phone"], text=text_msg)
            logger.info("Waitlist match WhatsApp gönderildi: patient=%s", patient_id)
    except Exception as e:
        logger.error("Waitlist match bildirimi başarısız: %s", e)
