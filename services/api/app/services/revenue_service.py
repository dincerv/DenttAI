"""
Recovered Revenue hesaplama servisi.

Mantık:
  1. 'match_found' bildirimi gönderilen ve CONFIRMED/COMPLETED olan randevuları bul.
  2. Her randevunun branşına göre SPECIALTY_FEE tarifesinden ücret ata.
  3. Toplam kurtarılan ciroyu döndür.
  4. Sonucu Redis'te 1 saat önbellekle.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import build_key, get_cache, set_cache
from app.core.config import settings
from app.queries import query_waitlist_fills
from app.schemas import RecoveredAppointment, RecoveredRevenueResponse


def _fee(specialty: str | None) -> float:
    if not specialty:
        return settings.SPECIALTY_FEE["default"]
    return settings.SPECIALTY_FEE.get(specialty, settings.SPECIALTY_FEE["default"])


async def get_recovered_revenue(
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> RecoveredRevenueResponse:
    cache_key = build_key("recovered_revenue", clinic_id, start_date, end_date)
    cached = await get_cache(cache_key)
    if cached:
        cached.pop("cached", None)
        return RecoveredRevenueResponse(**cached, cached=True)

    rows = await query_waitlist_fills(db, clinic_id, start_date, end_date)

    appointments: list[RecoveredAppointment] = []
    specialty_agg: dict[str, dict] = defaultdict(lambda: {"count": 0, "revenue": 0.0})

    for row in rows:
        fee = _fee(row.get("specialty"))
        appt = RecoveredAppointment(
            message_id=row["message_id"],
            sent_at=row["sent_at"],
            original_appointment_id=row["original_appointment_id"],
            specialty=row.get("specialty"),
            patient_name=row["patient_name"],
            fee=fee,
        )
        appointments.append(appt)
        sp = row.get("specialty") or "Belirtilmemiş"
        specialty_agg[sp]["count"] += 1
        specialty_agg[sp]["revenue"] += fee

    by_specialty = [
        {"specialty": sp, **vals}
        for sp, vals in sorted(specialty_agg.items(), key=lambda x: -x[1]["revenue"])
    ]
    total_revenue = sum(a.fee for a in appointments)

    response = RecoveredRevenueResponse(
        period_start=start_date,
        period_end=end_date,
        total_recovered_appointments=len(appointments),
        total_recovered_revenue=total_revenue,
        by_specialty=by_specialty,
        appointments=appointments,
        cached=False,
    )
    await set_cache(cache_key, response.model_dump())
    return response
