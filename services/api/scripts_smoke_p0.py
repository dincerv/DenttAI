"""Local smoke for backend P0 fixes — run in Docker."""
from app.celery_app import celery_app, shared_task, app

assert celery_app is app

from app.core.metrics import record_celery_task_result

record_celery_task_result("t", "ok", 0.1)

from app.providers.whatsapp_provider import WhatsappProvider

assert "facebook.com" in WhatsappProvider.BASE_URL
print("BASE", WhatsappProvider.BASE_URL)

from app.tasks.post_op_tasks import send_postop_followup_for_appointment

assert callable(send_postop_followup_for_appointment.delay)
print("postop.delay OK")

from app.tasks import appointment_tasks, whatsapp_tasks  # noqa: F401

print("tasks OK")

from app.services.whatsapp_service import process_incoming_whatsapp_message  # noqa: F401

print("ingest OK")

# SQL drift check
src = open("app/tasks/appointment_tasks.py", encoding="utf-8").read()
assert "p.phone_number" not in src
assert "p.phone AS phone_number" in src
print("phone column OK")


@shared_task(bind=True)
def _ping(self, x):
    return x + 1


print("delay", _ping.delay(1).result(timeout=10))
print("ALL_IMPORTS_OK")
