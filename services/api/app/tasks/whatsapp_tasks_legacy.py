"""WhatsApp background task handlers.

Keeps webhook HTTP router thin and isolates async processing logic behind
Celery task boundaries.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import text

from app.celery_app import celery_app
from app.core.database import AsyncSessionFactory
from app.core.metrics import record_celery_task_result
from app.models.whatsapp import PatientFeedback
from app.services.llm_service import ResponseType, get_llm_service

logger = logging.getLogger(__name__)

# Reuse one event loop per Celery worker process to prevent asyncpg/loop mismatch
# errors under burst loads.
_worker_loop: asyncio.AbstractEventLoop | None = None


def _run_worker_coro(coro):
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3)
def process_incoming_message(
    self,
    phone_number: str,
    message_id: str,
    timestamp: int,
    message_data: dict[str, Any],
):
    """Process an incoming WhatsApp message in background."""
    started_at = time.perf_counter()
    try:
        _run_worker_coro(
            _process_message_impl(
                phone_number=phone_number,
                message_id=message_id,
                timestamp=timestamp,
                message_data=message_data,
            )
        )
        record_celery_task_result(
            "process_incoming_message",
            "success",
            time.perf_counter() - started_at,
        )
    except Exception as exc:
        record_celery_task_result(
            "process_incoming_message",
            "retry",
            time.perf_counter() - started_at,
        )
        logger.error("Message processing failed: %s", exc)
        raise self.retry(exc=exc)


async def _process_message_impl(
    phone_number: str,
    message_id: str,
    timestamp: int,
    message_data: dict[str, Any],
):
    async with AsyncSessionFactory() as db:
        patient_result = await db.execute(
            text(
                """
                SELECT id, clinic_id FROM patients
                WHERE phone LIKE :phone
                LIMIT 1
                """
            ),
            {"phone": f"%{phone_number}%"},
        )
        patient_row = patient_result.fetchone()

        if not patient_row:
            logger.warning("Patient not found for phone: %s", phone_number)
            return

        patient_id, clinic_id = patient_row

        message_text = ""
        msg_type = message_data.get("type")

        if msg_type == "text":
            message_text = message_data.get("text", {}).get("body", "")
        elif msg_type == "button":
            message_text = message_data.get("button", {}).get("payload", "")

        if not message_text:
            logger.warning("No text content in message: %s", message_id)
            return

        logger.info("Processing message from %s: %s", patient_id, message_text[:50])

        llm = None
        try:
            llm = get_llm_service()
        except Exception as exc:
            logger.warning("LLM unavailable, falling back to keyword rules: %s", exc)

        appointment_result = await db.execute(
            text(
                """
                SELECT id, scheduled_at, doctor_id
                FROM appointments
                WHERE patient_id = :pid AND clinic_id = :cid
                  AND status IN ('scheduled', 'confirmed')
                ORDER BY scheduled_at DESC
                LIMIT 1
                """
            ),
            {"pid": str(patient_id), "cid": str(clinic_id)},
        )
        appt_row = appointment_result.fetchone()

        if appt_row:
            appt_id, scheduled_at, doctor_id = appt_row

            if llm:
                classification = await llm.classify_appointment_response(
                    patient_message=message_text,
                    appointment_details=f"Scheduled at {scheduled_at}",
                    clinic_name="DentAI",
                    language="en",
                )
                response_type = classification.get("type")
            else:
                lowered = message_text.lower()
                if any(k in lowered for k in ["cancel", "iptal"]):
                    response_type = ResponseType.CANCEL.value
                elif any(k in lowered for k in ["confirm", "ok", "gelece", "onay"]):
                    response_type = ResponseType.CONFIRM.value
                elif any(k in lowered for k in ["reschedule", "değiş", "ertele"]):
                    response_type = ResponseType.RESCHEDULE.value
                else:
                    response_type = ResponseType.OTHER.value

            if response_type == ResponseType.CANCEL.value:
                logger.info("Patient %s cancelled appointment %s", patient_id, appt_id)
                from app.tasks.appointment_tasks import process_appointment_cancellation

                process_appointment_cancellation.delay(str(appt_id))

            elif response_type == ResponseType.CONFIRM.value:
                await db.execute(
                    text(
                        """
                        UPDATE appointments
                        SET status = 'confirmed',
                            updated_at = NOW()
                        WHERE id = :appt_id
                        """
                    ),
                    {"appt_id": str(appt_id)},
                )
                await db.commit()
                logger.info("Appointment %s confirmed by patient", appt_id)

            elif response_type == ResponseType.RESCHEDULE.value:
                logger.info("Patient %s wants to reschedule: %s", patient_id, message_text)

        else:
            completed_result = await db.execute(
                text(
                    """
                    SELECT id FROM appointments
                    WHERE patient_id = :pid AND clinic_id = :cid
                      AND status = 'completed'
                    ORDER BY scheduled_at DESC
                    LIMIT 1
                    """
                ),
                {"pid": str(patient_id), "cid": str(clinic_id)},
            )
            completed_row = completed_result.fetchone()

            if completed_row:
                appointment_id = completed_row[0]

                if llm:
                    severity_result = await llm.classify_feedback_severity(
                        feedback_message=message_text,
                        feedback_type="general",
                        language="en",
                    )
                    severity = severity_result.get("severity", "medium")
                    requires_action = severity_result.get("requires_immediate_action", False)
                else:
                    lowered = message_text.lower()
                    severity = (
                        "critical"
                        if any(k in lowered for k in ["kanama", "bayıl", "nefes"])
                        else "medium"
                    )
                    requires_action = severity == "critical"

                feedback = PatientFeedback(
                    clinic_id=clinic_id,
                    appointment_id=appointment_id,
                    patient_id=patient_id,
                    feedback_type="other",
                    severity=severity,
                    message=message_text,
                    requires_action=requires_action,
                    channel="whatsapp",
                )
                db.add(feedback)
                await db.flush()

                logger.info("Feedback created: %s (severity: %s)", feedback.id, severity)

                if requires_action or severity in ["high", "critical"]:
                    logger.warning(
                        "ESCALATE: Feedback %s requires immediate attention", feedback.id
                    )

                await db.commit()

                # Dispatch AI-powered solution reply to the patient
                try:
                    from app.tasks.post_op_tasks import send_faq_response_to_patient
                    send_faq_response_to_patient.delay(
                        clinic_id=str(clinic_id),
                        patient_phone=phone_number,
                        patient_message=message_text,
                        feedback_id=str(feedback.id),
                    )
                except Exception as dispatch_err:
                    logger.warning(
                        "Could not dispatch faq_response task: %s", dispatch_err
                    )


__all__ = ["process_incoming_message"]
