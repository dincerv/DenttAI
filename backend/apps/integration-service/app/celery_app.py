"""
Celery Configuration — Distributed Task Queue Setup

Cloud-agnostic: Redis/RabbitMQ backend adaptable
"""
from kombu import Exchange, Queue
from celery import Celery
from celery.schedules import crontab

# ─────────────────────────────────────────────────────────────────────────────
# Celery Uygulama Yapılandırması
# ─────────────────────────────────────────────────────────────────────────────

from app.core.config import settings

celery_app = Celery(
    "dentai_flow",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BACKEND_URL,
    include=[
        "app.tasks.appointment_tasks",
        "app.tasks.whatsapp_tasks",
        "app.tasks.post_op_tasks",
    ],
)

celery_app.conf.update(
    # ──────────────── TASK ROUTING ────────────────
    task_routes={
        "app.tasks.appointment_tasks.*": {"queue": "appointments"},
        "app.tasks.whatsapp_tasks.process_incoming_message": {"queue": "whatsapp"},
        "app.tasks.whatsapp_tasks.*": {"queue": "whatsapp"},
        "webhook_tasks.*": {"queue": "whatsapp"},
    },
    
    # ──────────────── QUEUE DEFINITIONS ────────────────
    task_queues=(
        Queue("appointments", Exchange("appointments"), routing_key="appointments"),
        Queue("whatsapp", Exchange("whatsapp"), routing_key="whatsapp"),
        Queue("ai", Exchange("ai"), routing_key="ai"),
        Queue("default", Exchange("default"), routing_key="default"),
    ),
    
    # ──────────────── RETRY STRATEGY ────────────────
    task_autoretry_for=(Exception,),
    task_max_retries=5,
    task_default_retry_delay=60,  # 1 min (base; exponential backoff applied per-task)
    
    # ──────────────── EXECUTION SETTINGS ────────────────
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 min hard limit
    task_soft_time_limit=25 * 60,  # 25 min soft limit (SoftTimeLimitExceeded)
    
    # ──────────────── WORKER SETTINGS ────────────────
    worker_prefetch_multiplier=1,  # One task at a time (careful processing)
    worker_max_tasks_per_child=1000,  # Recycle worker after 1000 tasks
    
    # ──────────────── RESULT BACKEND ────────────────
    result_expires=3600,  # Results kept for 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",  # Redis Sentinel support
    },
    
    # ──────────────── PERIODIC TASKS (BEAT) ────────────────
    beat_schedule={
        # Her 5 dakikada yaklaşan randevuları kontrol et
        "check-upcoming-appointments": {
            "task": "app.tasks.appointment_tasks.send_appointment_reminders",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {
                "expires": 240,  # Expire after 4 min (don't overlap)
            },
        },
        # Her saat: süresi geçmiş feedback'leri kontrol et
        "check-overdue-feedback": {
            "task": "app.tasks.appointment_tasks.check_overdue_feedback",
            "schedule": crontab(minute=0),  # Every hour
            "options": {
                "expires": 3540,  # Expire after 59 min
            },
        },
    },
    
    # ──────────────── SERIALIZATION ────────────────
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Task Result Callbacks (Success/Failure Handing)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True)
def debug_task(self):
    """Debug task — health check"""
    print(f"Request: {self.request!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Environment-Based Configuration Override
# ─────────────────────────────────────────────────────────────────────────────

# Backward compatibility for modules importing `from app.celery_app import app`.
app = celery_app

__all__ = ["celery_app", "app"]
