"""
WhatsApp Ingestion Webhook — Meta Cloud API gelen mesajları alır.
Eski: Celery task dispatch (celery_client.send_task)
Yeni: FastAPI BackgroundTasks ile doğrudan async işlem
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["whatsapp-webhook-ingestion"])


def _verify_webhook_signature(body: bytes, signature: str | None, app_secret: str) -> bool:
    if not signature or not app_secret:
        return False

    if signature.startswith("sha256="):
        signature = signature[7:]

    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None,
):
    if hub_verify_token != settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid mode")

    return int(hub_challenge)


@router.post("/webhook", status_code=202)
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    x_hub_signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Hub-Signature")

    app_secret = settings.WHATSAPP_APP_SECRET or settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    if not _verify_webhook_signature(body, x_hub_signature, app_secret):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            messages = value.get("messages", [])
            statuses = value.get("statuses", [])

            for msg in messages:
                phone = msg.get("from")
                msg_id = msg.get("id")
                timestamp = msg.get("timestamp")

                # Celery yerine BackgroundTasks ile işle
                background_tasks.add_task(
                    _process_incoming_message,
                    phone_number=phone,
                    message_id=msg_id,
                    timestamp=timestamp,
                    message_data=msg,
                )

            for status_event in statuses:
                msg_id = status_event.get("id")
                status_value = status_event.get("status")
                background_tasks.add_task(_update_message_status_bg, msg_id, status_value)

    return {"status": "ok"}


async def _process_incoming_message(
    phone_number: str,
    message_id: str,
    timestamp: str,
    message_data: dict[str, Any],
) -> None:
    """
    Gelen WhatsApp mesajını işle.
    Eski: Celery task 'app.tasks.whatsapp_tasks.process_incoming_message'
    Yeni: Doğrudan async çağrı
    """
    try:
        from app.services.whatsapp_service import process_incoming_whatsapp_message  # lazy import
        await process_incoming_whatsapp_message(
            phone_number=phone_number,
            message_id=message_id,
            timestamp=timestamp,
            message_data=message_data,
        )
    except ImportError:
        # WhatsApp service henüz bu fonksiyonu implement etmemiş olabilir
        logger.info(f"WhatsApp mesajı alındı (işlem hazır değil): phone={phone_number}, id={message_id}")
    except Exception as e:
        logger.error(f"WhatsApp mesaj işleme hatası: {e}")


async def _update_message_status_bg(message_id: str, status: str) -> None:
    """Mesaj durumunu arka planda güncelle."""
    try:
        from app.core.database import AsyncSessionLocal
        status_map = {
            "sent": "sent",
            "delivered": "delivered",
            "read": "read",
            "failed": "failed",
        }
        db_status = status_map.get(status, "sent")

        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    """
                    UPDATE whatsapp_message_log
                    SET status = :status,
                        updated_at = NOW()
                    WHERE whatsapp_message_id = :msg_id
                    """
                ),
                {"status": db_status, "msg_id": message_id},
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Mesaj durumu güncelleme hatası: {e}")
