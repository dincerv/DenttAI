"""
Bildirim görevleri — APScheduler tarafından çağrılır.
Eski: notification-service (Node.js/BullMQ) + RabbitMQ consumers
Yeni: doğrudan Python async fonksiyonları
"""
import logging
from datetime import datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_appointment_reminder(
    appointment_id: str,
    clinic_id: str,
    patient_phone: str,
    patient_name: str,
    appointment_time: str,
) -> None:
    """
    Randevu hatırlatma mesajı gönderir.
    APScheduler job olarak çağrılır.
    """
    try:
        logger.info(
            f"WhatsApp hatırlatma gönderiliyor: "
            f"appointment_id={appointment_id}, phone={patient_phone}"
        )

        # Mesaj içeriği
        appt_dt = datetime.fromisoformat(appointment_time)
        message_body = (
            f"Sayın {patient_name},\n"
            f"Randevunuz yarın {appt_dt.strftime('%d.%m.%Y %H:%M')} tarihinde.\n"
            f"Kliniğimizi bekliyoruz! 🦷"
        )

        await _send_whatsapp_text(patient_phone, message_body)
        logger.info(f"Hatırlatma gönderildi: appointment_id={appointment_id}")

    except Exception as e:
        logger.error(f"Hatırlatma gönderme hatası (appointment_id={appointment_id}): {e}")
        raise  # APScheduler retry için


async def send_post_op_followup(
    appointment_id: str,
    clinic_id: str,
    patient_phone: str,
    patient_name: str,
    treatment_type: str,
) -> None:
    """
    Tedavi sonrası takip mesajı gönderir.
    APScheduler job olarak çağrılır (randevu bitiminden 24 saat sonra).
    """
    try:
        message_body = (
            f"Sayın {patient_name},\n"
            f"Dünkü {treatment_type} tedavinizin ardından nasılsınız? "
            f"Herhangi bir şikayetiniz varsa lütfen bizimle iletişime geçin."
        )

        await _send_whatsapp_text(patient_phone, message_body)
        logger.info(f"Post-op takip gönderildi: appointment_id={appointment_id}")

    except Exception as e:
        logger.error(f"Post-op takip hatası (appointment_id={appointment_id}): {e}")
        raise


async def _send_whatsapp_text(phone: str, message: str) -> dict:
    """
    WhatsApp Cloud API üzerinden text mesaj gönderir.
    Mock mode: WHATSAPP_ACCESS_TOKEN yoksa log'a yazar.
    """
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        # Mock mode — gerçek API çağrısı yok
        logger.info(f"[MOCK WhatsApp] → {phone}: {message[:80]}...")
        return {"status": "mock_sent"}

    url = (
        f"https://graph.facebook.com/v19.0/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone.replace("+", "").replace(" ", ""),
        "type": "text",
        "text": {"body": message},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if not response.is_success:
            error_body = response.text[:500]
            raise httpx.HTTPStatusError(
                f"{response.status_code} - {error_body}",
                request=response.request,
                response=response,
            )
        return response.json()
