"""
Celery Tasks — Appointment Reminders, Cancellation, Waitlist Offers

Async background jobs with retry strategy and error handling.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, text

from app.celery_app import celery_app
from app.core.database import AsyncSessionFactory
from app.models.whatsapp import (
    ClinicSettings,
    DoctorSettings,
    WhatsappMessageLog,
    WhatsappMessageStatus,
    PatientFeedback,
)
from app.providers.whatsapp_provider import (
    get_whatsapp_provider,
    WhatsappAPIError,
)
from app.core.metrics import record_celery_task_result
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SEND APPOINTMENT REMINDERS
# ═══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=300,  # 5 min
)
def send_appointment_reminders(self) -> dict[str, int]:
    """
    Scheduled task: Every 5 minutes, check for upcoming appointments
    and send WhatsApp reminders.
    
    Logic:
    1. Find appointments in next 2-24 hours
    2. Check clinic_settings.reminder_intervals
    3. Send templated message via WhatsApp
    4. Log to whatsapp_message_log with QUEUED status
    5. Return summary (sent count, failed count, skipped count)
    """
    import asyncio
    
    started_at = time.perf_counter()
    try:
        result = asyncio.run(_send_appointment_reminders_impl())
        record_celery_task_result(
            "send_appointment_reminders",
            "success",
            time.perf_counter() - started_at,
        )
        logger.info(f"Appointment reminders sent: {result}")
        return result
    except Exception as exc:
        record_celery_task_result(
            "send_appointment_reminders",
            "retry",
            time.perf_counter() - started_at,
        )
        logger.error(f"Appointment reminder task failed: {exc}")
        raise self.retry(exc=exc)


async def _send_appointment_reminders_impl() -> dict[str, int]:
    """Implementation logic."""
    stats = {"sent": 0, "failed": 0, "skipped": 0}
    
    async with AsyncSessionFactory() as db:
        # Find appointments in next 2-24 hours
        now = datetime.utcnow()
        window_start = now + timedelta(hours=2)
        window_end = now + timedelta(hours=24)
        
        result = await db.execute(
            text("""
                SELECT a.id, a.clinic_id, a.patient_id, a.scheduled_at,
                       a.doctor_id,
                       p.phone_number,
                       p.full_name   AS patient_name,
                       c.name        AS clinic_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN clinics  c ON a.clinic_id  = c.id
                WHERE a.scheduled_at >= :start
                  AND a.scheduled_at <= :end
                  AND a.status = 'scheduled'
                LIMIT 100
            """),
            {"start": window_start, "end": window_end},
        )
        rows = result.fetchall()

        # Try to initialise LLM once; fall back to templates if unavailable
        try:
            llm_service = get_llm_service()
        except Exception as exc:
            logger.warning("LLM unavailable for reminders, using templates: %s", exc)
            llm_service = None
        
        for row in rows:
            appointment_id = row[0]
            clinic_id     = row[1]
            patient_id    = row[2]
            scheduled_at  = row[3]
            doctor_id     = row[4]
            phone_number  = row[5]
            patient_name  = row[6] or "Hasta"
            clinic_name   = row[7] or "Klinik"
            
            try:
                # Get clinic settings
                clinic_result = await db.execute(
                    select(ClinicSettings).where(
                        ClinicSettings.clinic_id == clinic_id
                    )
                )
                settings = clinic_result.scalar_one_or_none()
                
                if not settings or not settings.is_whatsapp_enabled:
                    stats["skipped"] += 1
                    continue
                
                # Calculate which reminder to send
                hours_until = (scheduled_at - now).total_seconds() / 3600
                reminder_config = _get_reminder_config(
                    settings.reminder_intervals,
                    hours_until,
                )
                
                if not reminder_config:
                    stats["skipped"] += 1
                    continue

                # Idempotency check — skip if already sent for this appointment+interval
                existing = await db.execute(
                    text("""
                        SELECT id FROM whatsapp_message_log
                        WHERE idempotency_key = :key
                        LIMIT 1
                    """),
                    {"key": f"{clinic_id}:{patient_id}:{appointment_id}:reminder"},
                )
                if existing.fetchone():
                    stats["skipped"] += 1
                    continue

                # Fetch doctor name
                doctor_row = await db.execute(
                    text("SELECT full_name FROM doctors WHERE id = :did LIMIT 1"),
                    {"did": str(doctor_id)},
                )
                doctor_record = doctor_row.fetchone()
                doctor_name = doctor_record[0] if doctor_record else "Doktorunuz"

                # Get WhatsApp provider
                provider = get_whatsapp_provider(settings)

                # For confirmation-window (≤ 6 hrs), use AI personalized message
                # For advance reminders (> 6 hrs), use WhatsApp template
                if hours_until <= 6 and llm_service is not None:
                    ai_message = await llm_service.generate_appointment_confirmation_message(
                        patient_name=patient_name,
                        doctor_name=doctor_name,
                        appointment_date=scheduled_at.strftime("%d.%m.%Y"),
                        appointment_time=scheduled_at.strftime("%H:%M"),
                        clinic_name=clinic_name,
                        language="tr",
                    )
                    await provider.send_text_message(
                        phone_number=phone_number,
                        text=ai_message,
                    )
                    template_key = "ai_appointment_confirmation"
                else:
                    template_variables = {
                        "patient_name": patient_name,
                        "appointment_date": scheduled_at.strftime("%d.%m.%Y"),
                        "appointment_time": scheduled_at.strftime("%H:%M"),
                        "clinic_name": clinic_name,
                        "doctor_name": doctor_name,
                    }
                    template_key = reminder_config.get("template_key", "appointment_reminder")
                    await provider.send_message(
                        phone_number=phone_number,
                        template_name=template_key,
                        parameters=template_variables,
                    )
                
                # Log message
                msg_log = WhatsappMessageLog(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    phone_number=phone_number,
                    message_type="reminder",
                    template_key=template_key,
                    idempotency_key=f"{clinic_id}:{patient_id}:{appointment_id}:reminder",
                    status=WhatsappMessageStatus.SENT,
                    created_by="system",
                )
                db.add(msg_log)
                await db.flush()
                
                stats["sent"] += 1
                logger.info(f"Appointment reminder sent: {appointment_id}")
                
            except WhatsappAPIError as e:
                logger.error(f"WhatsApp send failed ({appointment_id}): {e}")
                stats["failed"] += 1
            except Exception as e:
                logger.error(f"Unexpected error ({appointment_id}): {e}")
                stats["failed"] += 1
        
        await db.commit()
    
    return stats


def _get_reminder_config(reminder_intervals: dict | None, hours_until: float) -> dict | None:
    """
    Determine which reminder should be sent based on time window.
    
    reminder_intervals = {
        "appointment_reminder": [
            {"hours_before": 24, "template_key": "reminder_24h"},
            {"hours_before": 2, "template_key": "reminder_2h"},
        ]
    }
    """
    if not reminder_intervals:
        return None
    
    reminders = reminder_intervals.get("appointment_reminder", [])
    for config in reminders:
        hours_before = config.get("hours_before")
        if hours_before and abs(hours_until - hours_before) < 1:  # ±1 hour window
            return config
    
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PROCESS CANCELLATION & OFFER WAITLIST SLOTS
# ═══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    default_retry_delay=60,
)
def process_appointment_cancellation(
    self,
    appointment_id: str,
    cancellation_reason: str = "patient_cancelled",
) -> dict[str, str]:
    """
    Process appointment cancellation and trigger waitlist offers.
    
    Flow:
    1. Mark appointment as CANCELLED
    2. Trigger offer_waitlist_slots task
    """
    import asyncio
    
    started_at = time.perf_counter()
    try:
        result = asyncio.run(
            _process_cancellation_impl(
                UUID(appointment_id),
                cancellation_reason,
            )
        )
        record_celery_task_result(
            "process_appointment_cancellation",
            "success",
            time.perf_counter() - started_at,
        )
        logger.info(f"Cancellation processed: {appointment_id}")
        return result
    except Exception as exc:
        record_celery_task_result(
            "process_appointment_cancellation",
            "retry",
            time.perf_counter() - started_at,
        )
        logger.error(f"Cancellation processing failed: {exc}")
        raise self.retry(exc=exc)


async def _process_cancellation_impl(
    appointment_id: UUID,
    cancellation_reason: str,
) -> dict[str, str]:
    """Implementation logic."""
    async with AsyncSessionFactory() as db:
        # Mark appointment as cancelled
        await db.execute(
            text("""
                UPDATE appointments
                SET status = 'cancelled',
                    updated_at = NOW()
                WHERE id = :appt_id
            """),
            {"appt_id": str(appointment_id)},
        )
        await db.commit()
    
    # Trigger waitlist offer job
    offer_waitlist_slots.delay(str(appointment_id))
    
    return {"status": "cancelled", "appointment_id": str(appointment_id)}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. OFFER WAITLIST SLOTS
# ═══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=120,
)
def offer_waitlist_slots(
    self,
    appointment_id: str,
) -> dict[str, int]:
    """
    Offer cancelled slot to waitlist patients.
    
    Flow:
    1. Get appointment details (date, time, doctor_id, specialty)
    2. Find waitlist patients matching specialty + preferred_doctor_ids
    3. Rank by: no-show history, response rate, preferred doctor
    4. Offer top N (e.g., 3) patients in sequence
    5. Wait 30 min per offer, advance if no response
    6. First to confirm → auto-fill appointment (is_auto_filled_by_ai = True)
    """
    import asyncio
    
    started_at = time.perf_counter()
    try:
        result = asyncio.run(
            _offer_waitlist_impl(UUID(appointment_id))
        )
        record_celery_task_result(
            "offer_waitlist_slots",
            "success",
            time.perf_counter() - started_at,
        )
        logger.info(f"Waitlist offers processed: {result}")
        return result
    except Exception as exc:
        record_celery_task_result(
            "offer_waitlist_slots",
            "retry",
            time.perf_counter() - started_at,
        )
        logger.error(f"Waitlist offer task failed: {exc}")
        raise self.retry(exc=exc)


async def _offer_waitlist_impl(appointment_id: UUID) -> dict[str, int]:
    """Implementation logic."""
    stats = {"offered": 0, "accepted": 0, "rejected": 0}
    
    async with AsyncSessionFactory() as db:
        # Get original appointment
        appt_result = await db.execute(
            text("""
                SELECT clinic_id, doctor_id, specialty, scheduled_at
                FROM appointments
                WHERE id = :appt_id AND status = 'cancelled'
            """),
            {"appt_id": str(appointment_id)},
        )
        appt_row = appt_result.fetchone()
        
        if not appt_row:
            logger.warning(f"Appointment not found or not cancelled: {appointment_id}")
            return stats
        
        clinic_id, doctor_id, specialty, scheduled_at = appt_row
        
        # Find waitlist patients
        waitlist_result = await db.execute(
            text("""
                SELECT w.id, w.patient_id, w.preferred_doctor_ids, p.phone_number
                FROM waitlist w
                JOIN patients p ON w.patient_id = p.id
                WHERE w.clinic_id = :clinic_id
                  AND w.specialty = :specialty
                  AND w.is_active = true
                ORDER BY w.priority ASC, w.created_at ASC
                LIMIT 10
            """),
            {
                "clinic_id": str(clinic_id),
                "specialty": specialty,
            },
        )
        waitlist_rows = waitlist_result.fetchall()
        
        llm_service = get_llm_service()
        clinic_settings_result = await db.execute(
            select(ClinicSettings).where(ClinicSettings.clinic_id == clinic_id)
        )
        clinic_settings = clinic_settings_result.scalar_one_or_none()
        provider = get_whatsapp_provider(clinic_settings)
        
        for idx, wl_row in enumerate(waitlist_rows[:3]):  # Top 3 offers
            waitlist_id = wl_row[0]
            patient_id = wl_row[1]
            preferred_doctors = wl_row[2] or []
            phone_number = wl_row[3]
            
            # Check if doctor is preferred
            doctor_match = not preferred_doctors or UUID(doctor_id) in preferred_doctors
            
            try:
                # Generate personalized message
                message = await llm_service.generate_waitlist_offer_message(
                    patient_name="Patient",
                    doctor_name="Dr. Khan",  # Fetch from DB
                    appointment_date=scheduled_at.strftime("%d.%m.%Y"),
                    appointment_time=scheduled_at.strftime("%H:%M"),
                    clinic_name="DentAI",
                    language="en",
                )
                
                # Send offer
                await provider.send_text_message(
                    phone_number=phone_number,
                    text=message,
                )
                
                # Log offer
                msg_log = WhatsappMessageLog(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    phone_number=phone_number,
                    message_type="waitlist_offer",
                    template_key="waitlist_offer",
                    idempotency_key=f"{clinic_id}:{patient_id}:{appointment_id}:offer_{idx}",
                    status=WhatsappMessageStatus.SENT,
                    created_by="system",
                )
                db.add(msg_log)
                await db.flush()
                
                stats["offered"] += 1
                logger.info(f"Waitlist offer sent to {patient_id}")
                
                # TODO: Set timeout (30 min) to move to next patient if no response
                
            except Exception as e:
                logger.error(f"Failed to offer waitlist slot ({patient_id}): {e}")
                stats["rejected"] += 1
        
        await db.commit()
    
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CHECK OVERDUE FEEDBACK
# ═══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=1,
    default_retry_delay=300,
)
def check_overdue_feedback(self) -> dict[str, int]:
    """
    Hourly task: Find overdue patient feedback and escalate to doctors.
    
    Escalation:
    - Feedback unresolved > 24h → notify assigned doctor
    - Feedback with requires_action=True → high priority alert
    """
    import asyncio
    
    started_at = time.perf_counter()
    try:
        result = asyncio.run(_check_overdue_impl())
        record_celery_task_result(
            "check_overdue_feedback",
            "success",
            time.perf_counter() - started_at,
        )
        logger.info(f"Feedback check completed: {result}")
        return result
    except Exception as exc:
        record_celery_task_result(
            "check_overdue_feedback",
            "retry",
            time.perf_counter() - started_at,
        )
        logger.error(f"Feedback check failed: {exc}")
        raise self.retry(exc=exc)


async def _check_overdue_impl() -> dict[str, int]:
    """Implementation logic."""
    stats = {"checked": 0, "escalated": 0}
    
    async with AsyncSessionFactory() as db:
        overdue_feedbacks = await db.execute(
            select(PatientFeedback).where(
                and_(
                    PatientFeedback.is_resolved == False,
                    PatientFeedback.created_at < (datetime.utcnow() - timedelta(hours=24)),
                )
            )
        )
        feedbacks = overdue_feedbacks.scalars().all()
        
        for feedback in feedbacks:
            # Send alert to assigned doctor
            if feedback.assigned_to_user_id:
                # TODO: Send notification (email/in-app)
                logger.warning(
                    f"Feedback escalation: {feedback.id} unresolved > 24h"
                )
                stats["escalated"] += 1
            
            stats["checked"] += 1
    
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "send_appointment_reminders",
    "process_appointment_cancellation",
    "offer_waitlist_slots",
    "check_overdue_feedback",
]
