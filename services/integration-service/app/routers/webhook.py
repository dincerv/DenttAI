"""
WhatsApp Webhook Handler — Process Incoming Messages

Webhook verification + async message processing with idempotency.
"""
from __future__ import annotations

import json
import logging
from typing import Optional, Any

from fastapi import APIRouter, Request, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.dependencies import get_db
from app.providers.whatsapp_provider import WhatsappProvider
from app.tasks.whatsapp_tasks import process_incoming_message
from app.core.config import settings
from app.core.metrics import record_webhook_dispatch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp-webhook"])


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class WhatsappWebhookMessage(BaseModel):
    """Incoming WhatsApp message from Meta."""
    from_: str = Field(..., alias="from")
    id: str
    timestamp: int
    type: str  # "text", "image", "location", etc.
    text: Optional[dict[str, str]] = None


class WhatsappWebhookContact(BaseModel):
    """Sender contact info."""
    profile: dict[str, str]
    wa_id: str


class WhatsappWebhookEntry(BaseModel):
    """Webhook entry (batch of messages)."""
    id: str
    changes: list[dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/webhook",
    summary="WhatsApp Webhook Verification",
    description="Meta sends verification challenge during webhook setup",
)
async def verify_webhook(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None,
):
    """
    Webhook verification endpoint.
    
    Meta sends GET request with:
    - hub.mode = "subscribe"
    - hub.challenge = <random string>
    - hub.verify_token = <configured token>
    
    We respond with the challenge to prove we own the endpoint.
    """
    if hub_verify_token != settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        logger.warning("Invalid webhook verify token")
        raise HTTPException(status_code=403, detail="Invalid token")
    
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    logger.info("Webhook verified")
    return int(hub_challenge)


@router.post(
    "/webhook",
    status_code=202,
    summary="WhatsApp Webhook Event Handler",
    description="Receive incoming messages and delivery/read receipts",
)
async def handle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Process incoming WhatsApp events.
    
    Meta sends POST with:
    - X-Hub-Signature header (HMAC-SHA256 signed request)
    - JSON body with messages, statuses, etc.
    
    We:
    1. Verify signature
    2. Parse incoming message
    3. Determine intent (confirm/cancel/reschedule/feedback)
    4. Trigger appropriate task (cancellation, feedback creation, etc.)
    5. Respond with 200 to Meta (ack)
    """
    body = await request.body()
    x_hub_signature = (
        request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Hub-Signature")
    )
    
    # Verify signature
    if not WhatsappProvider.verify_webhook_signature(
        body=body,
        signature=x_hub_signature,
        app_secret=(settings.WHATSAPP_APP_SECRET or settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN),
    ):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse JSON
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Process events
    
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            
            messages = value.get("messages", [])
            statuses = value.get("statuses", [])
            
            # Handle incoming messages
            for msg in messages:
                phone = msg.get("from")
                msg_id = msg.get("id")
                timestamp = msg.get("timestamp")
                
                # Dispatch async processing safely (don't fail webhook ack)
                try:
                    process_incoming_message.delay(
                        phone_number=phone,
                        message_id=msg_id,
                        timestamp=timestamp,
                        message_data=msg,
                    )
                    record_webhook_dispatch("success")
                except Exception:
                    record_webhook_dispatch("failed")
                    logger.exception("Failed to dispatch process_incoming_message task")
            
            # Handle delivery/read receipts
            for status_event in statuses:
                msg_id = status_event.get("id")
                status_value = status_event.get("status")  # "sent", "delivered", "read"
                
                # Update message log in-request to avoid detached-session failures
                try:
                    await _update_message_status(db, msg_id, status_value)
                except Exception:
                    logger.exception("Failed to update message status")
    
    # Always return 200 to Meta (prevent retries)
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Update Message Status
# ═══════════════════════════════════════════════════════════════════════════════

async def _update_message_status(
    db: AsyncSession,
    message_id: str,
    status: str,
):
    """Update WhatsApp message delivery status in DB."""
    from app.models.whatsapp import WhatsappMessageLog, WhatsappMessageStatus
    
    status_map = {
        "sent": WhatsappMessageStatus.SENT,
        "delivered": WhatsappMessageStatus.DELIVERED,
        "read": WhatsappMessageStatus.READ,
        "failed": WhatsappMessageStatus.FAILED,
    }
    
    db_status = status_map.get(status, WhatsappMessageStatus.SENT)
    
    await db.execute(
        text("""
            UPDATE whatsapp_message_log
            SET status = :status,
                updated_at = NOW()
            WHERE whatsapp_message_id = :msg_id
        """),
        {"status": db_status.value, "msg_id": message_id},
    )
    await db.commit()


__all__ = ["router"]
