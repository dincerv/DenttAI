"""
Sync Scheduler — 30 dakikada bir tüm aktif entegrasyonları senkronize eder.

asyncio background task olarak çalışır, FastAPI lifespan ile yönetilir.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.database import AsyncSessionFactory
from app.services.sync_engine import sync_all_active

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
SYNC_INTERVAL_SECONDS = 30 * 60  # 30 dakika


async def _scheduler_loop():
    """Her 30 dakikada bir tüm aktif entegrasyonları senkronize et."""
    while True:
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
        logger.info("Zamanlanmış sync başlatılıyor...")
        try:
            async with AsyncSessionFactory() as db:
                results = await sync_all_active(db)
                total = len(results)
                errors = sum(1 for r in results if r.errors)
                logger.info(
                    "Zamanlanmış sync tamamlandı: %d klinik, %d hata",
                    total, errors,
                )
        except Exception:
            logger.exception("Zamanlanmış sync hatası")


def start_scheduler():
    """Scheduler background task'ını başlat."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_scheduler_loop())
        logger.info("Sync scheduler başlatıldı (interval=%ds)", SYNC_INTERVAL_SECONDS)


def stop_scheduler():
    """Scheduler'ı durdur."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        logger.info("Sync scheduler durduruldu")
        _task = None
