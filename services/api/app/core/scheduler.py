"""
APScheduler — RabbitMQ + BullMQ + Celery'nin yerine geçen async scheduler.

Randevu hatırlatmaları ve post-op follow-up'lar bu scheduler üzerinden
zamanlanır. Monolith içinde doğrudan Python async fonksiyonları çağrılır.

Job Persistence: Redis job store kullanılır. Böylece uygulama yeniden
başladığında planlanmış job'lar kaybolmaz.
"""
from __future__ import annotations

import logging
import ssl
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_jobstore():
    """REDIS_URL'den (redis:// veya rediss://) job store oluştur."""
    url = (settings.REDIS_URL or "").strip()
    if not url:
        logger.warning("REDIS_URL boş — MemoryJobStore kullanılıyor")
        return MemoryJobStore()

    parsed = urlparse(url)
    if parsed.scheme not in ("redis", "rediss"):
        logger.warning("Geçersiz REDIS_URL şeması (%s) — MemoryJobStore", parsed.scheme)
        return MemoryJobStore()

    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    password = parsed.password
    # Upstash yalnızca db 0 destekler; path yoksa 0
    db = 0
    if parsed.path and parsed.path.strip("/"):
        try:
            db = int(parsed.path.strip("/").split("/")[0])
        except ValueError:
            db = 0
    if parsed.scheme == "rediss":
        db = 0  # Upstash

    connect_args: dict = {
        "host": host,
        "port": port,
        "db": db,
        "password": password,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
    }
    if parsed.scheme == "rediss":
        connect_args["ssl"] = True
        connect_args["ssl_cert_reqs"] = ssl.CERT_NONE

    logger.info("APScheduler Redis job store: %s:%s db=%s ssl=%s", host, port, db, parsed.scheme == "rediss")
    try:
        import redis as _redis
        test_client = _redis.StrictRedis(**{k: v for k, v in connect_args.items()
                                            if k not in ("socket_connect_timeout", "socket_timeout")},
                                         socket_connect_timeout=3, socket_timeout=3)
        test_client.ping()
        test_client.close()
    except Exception as e:
        logger.warning("Redis ping başarısız (%s) — MemoryJobStore kullanılıyor", e)
        return MemoryJobStore()

    return RedisJobStore(
        jobs_key="dentai:apscheduler:jobs",
        run_times_key="dentai:apscheduler:run_times",
        **connect_args,
    )


_jobstores = {"default": _build_jobstore()}

_executors = {
    "default": AsyncIOExecutor(),
}

scheduler = AsyncIOScheduler(
    jobstores=_jobstores,
    executors=_executors,
    job_defaults={
        "coalesce": True,
        "max_instances": 3,
        "misfire_grace_time": 60 * 60,
    },
    timezone="Europe/Istanbul",
)


async def start_scheduler() -> None:
    """Uygulama başlarken çağrılır. Redis hata verirse MemoryJobStore'a düşer."""
    try:
        scheduler.start()
        logger.info("APScheduler başlatıldı")
    except Exception as e:
        logger.error("APScheduler Redis ile başlatılamadı: %s — memory fallback", e)
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
        except Exception:
            pass
        scheduler.configure(jobstores={"default": MemoryJobStore()})
        scheduler.start()
        logger.warning("APScheduler MemoryJobStore ile başlatıldı (job'lar restart'ta kaybolur)")


async def stop_scheduler() -> None:
    """Uygulama kapanırken çağrılır."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler durduruldu")


def schedule_whatsapp_reminder(
    appointment_id: UUID,
    clinic_id: UUID,
    patient_phone: str,
    patient_name: str,
    appointment_time: datetime,
    reminder_minutes_before: int = 60,
) -> str | None:
    """
    Randevu öncesi WhatsApp hatırlatması zamanlar.
    Returns job_id or None if scheduling fails.
    """
    from app.tasks.notification_tasks import send_appointment_reminder  # lazy import

    import pytz

    tz = pytz.timezone("Europe/Istanbul")
    run_time = appointment_time
    if run_time.tzinfo is None:
        run_time = tz.localize(run_time)

    reminder_time = run_time - timedelta(minutes=reminder_minutes_before)
    now = datetime.now(tz)
    if reminder_time <= now:
        logger.debug("Hatırlatma zamanı geçmiş, job eklenmedi: appointment_id=%s", appointment_id)
        return None

    job_id = f"reminder_{appointment_id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        send_appointment_reminder,
        trigger="date",
        run_date=reminder_time,
        id=job_id,
        kwargs={
            "appointment_id": str(appointment_id),
            "clinic_id": str(clinic_id),
            "patient_phone": patient_phone,
            "patient_name": patient_name,
            "appointment_time": appointment_time.isoformat(),
        },
    )
    logger.info("WhatsApp hatırlatma zamanlandı: %s → %s", job_id, reminder_time)
    return job_id


def cancel_whatsapp_reminder(appointment_id: UUID) -> bool:
    """Randevu iptal edildiğinde zamanlanmış hatırlatmayı kaldır."""
    job_id = f"reminder_{appointment_id}"
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)
        logger.info("WhatsApp hatırlatma iptal edildi: %s", job_id)
        return True
    return False
