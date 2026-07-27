"""
Appointment Service — İş Mantığı Katmanı
Sorumluluk: Randevu CRUD, iptal tespiti, WaitlistEngine tetikleme.
"""
from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.broker import publish_event
from app.models.appointment import Appointment, AppointmentStatus
from app.models.waitlist import Waitlist
from app.schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdateRequest,
)

logger = logging.getLogger(__name__)


async def _check_appointment_overlap(
    doctor_id: UUID,
    scheduled_at: datetime,
    duration_minutes: int,
    clinic_id: UUID,
    db: AsyncSession,
    exclude_appointment_id: UUID | None = None,
) -> bool:
    """
    Aynı hekimde çakışan randevu var mı kontrol et.
    Çakışma varsa True döner.
    """
    from datetime import timedelta
    
    # Appointment end time
    end_time = scheduled_at + timedelta(minutes=duration_minutes)
    
    query = '''
    SELECT COUNT(*) as count FROM appointments
    WHERE doctor_id = :doctor_id
      AND clinic_id = :clinic_id
      AND status NOT IN ('cancelled')
      AND (
        (scheduled_at < :end_time AND scheduled_at + (INTERVAL '1 minute' * duration_minutes) > :start_time)
      )
    '''
    
    params = {
        'doctor_id': str(doctor_id),
        'clinic_id': str(clinic_id),
        'start_time': scheduled_at,
        'end_time': end_time,
    }
    
    if exclude_appointment_id:
        query += ' AND id != CAST(:exclude_id AS uuid)'
        params['exclude_id'] = str(exclude_appointment_id)
    
    result = await db.execute(text(query), params)
    count = result.scalar_one_or_none() or 0
    return count > 0


async def _acquire_doctor_schedule_lock(
    clinic_id: UUID,
    doctor_id: UUID,
    db: AsyncSession,
) -> None:
    """
    Aynı klinik+doktor için oluşturma/güncelleme işlemlerini serialize eder.
    Böylece eşzamanlı isteklerde çakışan randevu yaratılması engellenir.
    """
    lock_key = f"appointment-lock:{clinic_id}:{doctor_id}"
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": lock_key},
    )


async def create_appointment(
    data: AppointmentCreateRequest,
    clinic_id: UUID,
    db: AsyncSession,
) -> AppointmentResponse:
    await _acquire_doctor_schedule_lock(clinic_id, data.doctor_id, db)

    # Overlap kontrolü
    has_overlap = await _check_appointment_overlap(
        doctor_id=data.doctor_id,
        scheduled_at=data.scheduled_at,
        duration_minutes=data.duration_minutes,
        clinic_id=clinic_id,
        db=db,
    )
    
    if has_overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu zaman aralığında hekim zaten bir randevusu var. Lütfen başka bir zaman seçiniz.",
        )
    
    appointment = Appointment(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        specialty=data.specialty,
        scheduled_at=data.scheduled_at,
        duration_minutes=data.duration_minutes,
        is_new_patient=data.is_new_patient,
        treatment_follow_up_enabled=data.treatment_follow_up_enabled,
        type=data.type,
        notes=data.notes,
    )
    db.add(appointment)
    await db.flush()  # id üretilsin ama commit beklensin
    await db.refresh(appointment)
    return AppointmentResponse.model_validate(appointment)


async def list_appointments(
    clinic_id: UUID,
    db: AsyncSession,
    specialty: str | None = None,
    status_filter: AppointmentStatus | None = None,
    skip: int = 0,
    limit: int = 200,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    doctor_id: str | None = None,
) -> AppointmentListResponse:
    # Base COUNT
    count_sql = """
        SELECT COUNT(*) FROM appointments
        WHERE clinic_id = :clinic_id
        {specialty_filter}
        {status_filter}
        {date_from_filter}
        {date_to_filter}
        {doctor_filter}
    """
    # Base SELECT — join doctors + patients for names
    select_sql = """
        SELECT
            a.id, a.clinic_id, a.patient_id, a.doctor_id, a.specialty,
            a.scheduled_at, a.duration_minutes, a.is_new_patient, a.treatment_follow_up_enabled, a.status, a.type, a.notes, a.created_at, a.updated_at,
            d.full_name  AS doctor_name,
            p.full_name  AS patient_name,
            p.phone      AS patient_phone
        FROM appointments a
        LEFT JOIN doctors  d ON d.id = a.doctor_id
        LEFT JOIN patients p ON p.id = a.patient_id
        WHERE a.clinic_id = :clinic_id
        {specialty_filter}
        {status_filter}
        {date_from_filter}
        {date_to_filter}
        {doctor_filter}
        ORDER BY a.scheduled_at
        OFFSET :skip LIMIT :limit
    """

    sf = "AND a.specialty = :specialty" if specialty else ""
    stf = "AND a.status = :status" if status_filter else ""
    dff = "AND a.scheduled_at >= :date_from" if date_from else ""
    dtf = "AND a.scheduled_at < :date_to" if date_to else ""
    df = "AND a.doctor_id = CAST(:doctor_id AS uuid)" if doctor_id else ""

    params: dict = {"clinic_id": str(clinic_id), "skip": skip, "limit": limit}
    if specialty:
        params["specialty"] = specialty
    if status_filter:
        params["status"] = status_filter.value
    if date_from:
        params["date_from"] = datetime.fromisoformat(date_from)
    if date_to:
        params["date_to"] = datetime.fromisoformat(date_to)
    if doctor_id:
        params["doctor_id"] = doctor_id

    total_result = await db.execute(
        text(count_sql.format(
            specialty_filter=sf.replace("a.", ""),
            status_filter=stf.replace("a.", ""),
            date_from_filter=dff.replace("a.", ""),
            date_to_filter=dtf.replace("a.", ""),
            doctor_filter=df.replace("a.", ""),
        )),
        params,
    )
    total = total_result.scalar_one()

    rows = (await db.execute(text(select_sql.format(
        specialty_filter=sf, status_filter=stf,
        date_from_filter=dff, date_to_filter=dtf, doctor_filter=df,
    )), params)).mappings().all()

    items = [
        AppointmentResponse(
            id=r["id"],
            clinic_id=r["clinic_id"],
            patient_id=r["patient_id"],
            doctor_id=r["doctor_id"],
            specialty=r["specialty"],
            scheduled_at=r["scheduled_at"],
            duration_minutes=r["duration_minutes"],
            is_new_patient=r["is_new_patient"],
            treatment_follow_up_enabled=r["treatment_follow_up_enabled"],
            status=r["status"],
            type=r["type"],
            notes=r["notes"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            doctor_name=r["doctor_name"],
            patient_name=r["patient_name"],
            patient_phone=r["patient_phone"],
        )
        for r in rows
    ]
    return AppointmentListResponse(items=items, total=total)


async def get_appointment(
    appointment_id: UUID,
    clinic_id: UUID,
    db: AsyncSession,
) -> AppointmentResponse:
    row = await _fetch_or_404(appointment_id, clinic_id, db)
    return AppointmentResponse.model_validate(row)


async def update_appointment(
    appointment_id: UUID,
    clinic_id: UUID,
    data: AppointmentUpdateRequest,
    db: AsyncSession,
) -> AppointmentResponse:
    appointment = await _fetch_or_404(appointment_id, clinic_id, db)

    prev_status = appointment.status
    
    # Overlap kontrolü: saat/süre/doktor değişimi varsa
    if (
        data.scheduled_at is not None
        or data.duration_minutes is not None
        or data.doctor_id is not None
    ):
        new_scheduled_at = data.scheduled_at if data.scheduled_at is not None else appointment.scheduled_at
        new_duration_minutes = data.duration_minutes if data.duration_minutes is not None else appointment.duration_minutes
        new_doctor_id = data.doctor_id if data.doctor_id is not None else appointment.doctor_id

        await _acquire_doctor_schedule_lock(clinic_id, new_doctor_id, db)
        
        has_overlap = await _check_appointment_overlap(
            doctor_id=new_doctor_id,
            scheduled_at=new_scheduled_at,
            duration_minutes=new_duration_minutes,
            clinic_id=clinic_id,
            db=db,
            exclude_appointment_id=appointment_id,
        )
        
        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu zaman aralığında hekim zaten bir randevusu var. Lütfen başka bir zaman seçiniz.",
            )

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(appointment, field, value)

    await db.flush()
    await db.refresh(appointment)

    # ── İptal tespiti → WaitlistEngine tetikle ──────────
    if (
        data.status == AppointmentStatus.CANCELLED
        and prev_status != AppointmentStatus.CANCELLED
    ):
        logger.info(
            "Randevu iptal edildi: %s | branş: %s",
            appointment_id,
            appointment.specialty,
        )
        await _handle_cancellation(appointment, db)

    # ── Teyit tespiti → Notification zamanlaması ─────────
    if (
        data.status == AppointmentStatus.CONFIRMED
        and prev_status != AppointmentStatus.CONFIRMED
    ):
        await publish_event(
            routing_key="appointment.confirmed",
            payload={
                "event": "appointment.confirmed",
                "clinic_id": str(appointment.clinic_id),
                "appointment_id": str(appointment.id),
                "patient_id": str(appointment.patient_id),
                "doctor_id": str(appointment.doctor_id),
                "specialty": appointment.specialty,
                "scheduled_at": appointment.scheduled_at.isoformat(),
            },
        )
        logger.info("Randevu teyit edildi: %s", appointment_id)

    # ── Tamamlama tespiti → Post-Op zamanlaması ────────
    if (
        data.status == AppointmentStatus.COMPLETED
        and prev_status != AppointmentStatus.COMPLETED
    ):
        await publish_event(
            routing_key="appointment.completed",
            payload={
                "event": "appointment.completed",
                "clinic_id": str(appointment.clinic_id),
                "appointment_id": str(appointment.id),
                "patient_id": str(appointment.patient_id),
                "doctor_id": str(appointment.doctor_id),
                "specialty": appointment.specialty,
                "completed_at": appointment.updated_at.isoformat(),
            },
        )
        logger.info("Randevu tamamlandı; post-op zamanlanıyor: %s", appointment_id)

    return AppointmentResponse.model_validate(appointment)


async def delete_appointment(
    appointment_id: UUID,
    clinic_id: UUID,
    db: AsyncSession,
) -> None:
    appointment = await _fetch_or_404(appointment_id, clinic_id, db)
    await db.delete(appointment)


# ── WaitlistEngine Entegrasyonu ───────────────────────────

async def _handle_cancellation(
    appointment: Appointment,
    db: AsyncSession,
) -> None:
    """
    İptal edilen randevu için:
    1. Aynı branşta en yüksek öncelikli yedek hastayı bul.
    2. Eşleşme varsa → waitlist.match_found event'i yayınla.
    3. Eşleşme yoksa → appointment.cancelled event'i yayınla.
    """
    # Yedek listede aynı branşta aktif, en yüksek öncelikli hasta
    match_query = (
        select(Waitlist)
        .where(
            Waitlist.clinic_id == appointment.clinic_id,
            Waitlist.specialty == appointment.specialty,
            Waitlist.is_active.is_(True),
        )
        .order_by(Waitlist.priority.asc())  # priority 1 = en yüksek
        .limit(1)
    )
    match: Waitlist | None = (await db.execute(match_query)).scalars().first()

    if match:
        # Yedek hastayı pasif yap (slot rezerve edildi)
        match.is_active = False
        await db.flush()

        await publish_event(
            routing_key="waitlist.match_found",
            payload={
                "event": "waitlist.match_found",
                "clinic_id": str(appointment.clinic_id),
                "cancelled_appointment_id": str(appointment.id),
                "patient_id": str(match.patient_id),
                "waitlist_id": str(match.id),
                "specialty": appointment.specialty,
                "original_slot": appointment.scheduled_at.isoformat(),
                "doctor_id": str(appointment.doctor_id),
                "priority": match.priority,
            },
        )
        logger.info(
            "Yedek eşleşme bulundu: waitlist_id=%s patient_id=%s",
            match.id,
            match.patient_id,
        )
    else:
        # Eşleşme yok — sadece iptal bildirimi
        await publish_event(
            routing_key="appointment.cancelled",
            payload={
                "event": "appointment.cancelled",
                "clinic_id": str(appointment.clinic_id),
                "appointment_id": str(appointment.id),
                "patient_id": str(appointment.patient_id),
                "doctor_id": str(appointment.doctor_id),
                "specialty": appointment.specialty,
                "scheduled_at": appointment.scheduled_at.isoformat(),
            },
        )
        logger.info("Eşleşme bulunamadı; iptal eventi yayınlandı: %s", appointment.id)


# ── Yardımcı ─────────────────────────────────────────────

async def _fetch_or_404(
    appointment_id: UUID,
    clinic_id: UUID,
    db: AsyncSession,
) -> Appointment:
    row = await db.get(Appointment, appointment_id)
    if not row or row.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Randevu bulunamadı",
        )
    return row
