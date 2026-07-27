from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.metrics import record_webhook_dispatch

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp-webhook-ingestion"])

celery_client = Celery(
    "whatsapp_ingestion",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BACKEND_URL,
)


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
async def handle_webhook(request: Request, db: AsyncSession = Depends(get_db)):
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

                try:
                    celery_client.send_task(
                        "app.tasks.whatsapp_tasks.process_incoming_message",
                        kwargs={
                            "phone_number": phone,
                            "message_id": msg_id,
                            "timestamp": timestamp,
                            "message_data": msg,
                        },
                        queue="whatsapp",
                    )
                    record_webhook_dispatch("success")
                except Exception:
                    record_webhook_dispatch("failed")
                    logger.exception("Failed to dispatch process_incoming_message task")

            for status_event in statuses:
                msg_id = status_event.get("id")
                status_value = status_event.get("status")
                try:
                    await _update_message_status(db, msg_id, status_value)
                except Exception:
                    logger.exception("Failed to update message status")

    return {"status": "ok"}


async def _update_message_status(db: AsyncSession, message_id: str, status: str):
    status_map = {
        "sent": "sent",
        "delivered": "delivered",
        "read": "read",
        "failed": "failed",
    }
    db_status = status_map.get(status, "sent")

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
