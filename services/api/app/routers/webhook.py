"""
WhatsApp Webhook — Legacy path alias
====================================
Canonical Meta webhook: GET/POST /api/whatsapp/webhook  (whatsapp_ingest.py)

Bu router eski path'i korur:
  GET/POST /api/integration/webhook/webhook

İkisi de aynı işleyiciyi kullanır — çift implementasyon yok.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.routers.whatsapp_ingest import handle_webhook as _handle_webhook
from app.routers.whatsapp_ingest import verify_webhook as _verify_webhook

router = APIRouter(prefix="/integration/webhook", tags=["whatsapp-webhook-alias"])


@router.get("/webhook", summary="WhatsApp Webhook Verification (alias)")
async def verify_webhook(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None,
):
    return await _verify_webhook(
        hub_mode=hub_mode,
        hub_challenge=hub_challenge,
        hub_verify_token=hub_verify_token,
    )


@router.post("/webhook", status_code=202, summary="WhatsApp Webhook Event Handler (alias)")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    return await _handle_webhook(request, background_tasks, db)
