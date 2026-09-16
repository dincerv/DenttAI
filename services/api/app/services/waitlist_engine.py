"""
WaitlistEngine — Yedek Liste Servis Katmanı
Sorumluluk: Yedek listesi CRUD, manuel eşleştirme, öncelik yönetimi.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waitlist import Waitlist
from app.schemas.waitlist import (
    WaitlistAddRequest,
    WaitlistMatchResponse,
    WaitlistResponse,
    WaitlistUpdateRequest,
)

logger = logging.getLogger(__name__)


async def add_to_waitlist(
    data: WaitlistAddRequest,
    clinic_id: UUID,
    db: AsyncSession,
) -> WaitlistResponse:
    """Yedek listeye yeni bir hasta ekler."""
    # Aynı hasta zaten bu branş için aktif listede mi?
    existing = await db.execute(
        select(Waitlist).where(
            Waitlist.clinic_id == clinic_id,
            Waitlist.patient_id == data.patient_id,
            Waitlist.specialty == data.specialty,
            Waitlist.is_active.is_(True),
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu hasta bu branş için zaten yedek listesinde.",
        )

    entry = Waitlist(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        specialty=data.specialty,
        priority=data.priority,
        preferred_days=data.preferred_days,
        notes=data.notes,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return WaitlistResponse.model_validate(entry)


async def list_waitlist(
    clinic_id: UUID,
    db: AsyncSession,
    specialty: str | None = None,
    active_only: bool = True,
) -> list[WaitlistResponse]:
    """Yedek listeyi zenginleştirilmiş bilgilerle döndürür."""
    sql = """
        SELECT
            w.id, w.clinic_id, w.patient_id, w.doctor_id, w.specialty,
            w.priority, w.is_active, w.preferred_days, w.notes, w.created_at,
            p.full_name  AS patient_name,
            p.notes      AS patient_notes,
            d.full_name  AS doctor_name,
            (
                SELECT MIN(a.scheduled_at)
                FROM appointments a
                WHERE a.patient_id = w.patient_id
                  AND a.clinic_id  = w.clinic_id
                  AND a.scheduled_at > NOW()
                  AND a.status IN ('scheduled', 'confirmed')
            ) AS next_appointment_date
        FROM waitlist w
        LEFT JOIN patients p ON p.id = w.patient_id
        LEFT JOIN doctors  d ON d.id = w.doctor_id
        WHERE w.clinic_id = :clinic_id
        {specialty_filter}
        {active_filter}
        ORDER BY w.priority ASC, w.created_at ASC
    """
    sf = "AND w.specialty = :specialty" if specialty else ""
    af = "AND w.is_active = true" if active_only else ""
    params: dict = {"clinic_id": str(clinic_id)}
    if specialty:
        params["specialty"] = specialty

    rows = (await db.execute(
        text(sql.format(specialty_filter=sf, active_filter=af)), params
    )).mappings().all()

    return [
        WaitlistResponse(
            id=r["id"],
            clinic_id=r["clinic_id"],
            patient_id=r["patient_id"],
            doctor_id=r["doctor_id"],
            specialty=r["specialty"],
            priority=r["priority"],
            is_active=r["is_active"],
            preferred_days=r.get("preferred_days"),
            notes=r.get("notes"),
            created_at=r["created_at"],
            patient_name=r.get("patient_name"),
            patient_notes=r.get("patient_notes"),
            doctor_name=r.get("doctor_name"),
            next_appointment_date=(
                r["next_appointment_date"].isoformat()
                if r.get("next_appointment_date") else None
            ),
        )
        for r in rows
    ]


async def update_waitlist_entry(
    entry_id: UUID,
    clinic_id: UUID,
    data: WaitlistUpdateRequest,
    db: AsyncSession,
) -> WaitlistResponse:
    entry = await _fetch_or_404(entry_id, clinic_id, db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(entry, field, value)
    await db.flush()
    await db.refresh(entry)
    return WaitlistResponse.model_validate(entry)


async def remove_from_waitlist(
    entry_id: UUID,
    clinic_id: UUID,
    db: AsyncSession,
) -> None:
    """Yedek listeden pasif yap (soft delete)."""
    entry = await _fetch_or_404(entry_id, clinic_id, db)
    entry.is_active = False
    await db.flush()


# ── Yardımcı ─────────────────────────────────────────────

async def _fetch_or_404(
    entry_id: UUID,
    clinic_id: UUID,
    db: AsyncSession,
) -> Waitlist:
    row = await db.get(Waitlist, entry_id)
    if not row or row.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yedek liste kaydı bulunamadı",
        )
    return row
