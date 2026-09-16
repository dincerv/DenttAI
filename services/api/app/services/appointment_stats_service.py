"""
Randevu istatistikleri servisi (saf Python ile özet hesaplama).

Pandas kaldırıldı: branş oranları için küçük bir satır setine pandas yüklemek
async route handler'ı blokluyordu. Saf Python hesaplamayla aynı sonuç elde edilir.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import build_key, get_cache, set_cache
from app.queries import query_appointment_stats, query_appointments_by_specialty
from app.schemas import AppointmentStatsResponse, SpecialtyStats


def _safe_pct(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 1)


async def get_appointment_stats(
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession,
    doctor_id: UUID | None = None,
) -> AppointmentStatsResponse:
    cache_key = build_key("appt_stats", clinic_id, str(doctor_id or "all"), start_date, end_date)
    cached = await get_cache(cache_key)
    if cached:
        cached.pop("cached", None)
        return AppointmentStatsResponse(**cached, cached=True)

    totals, specialty_rows = await _fetch_raw(db, clinic_id, start_date, end_date, doctor_id=doctor_id)

    total = int(totals.get("total") or 0)
    cancelled = int(totals.get("cancelled") or 0)
    no_show = int(totals.get("no_show") or 0)
    completed = int(totals.get("completed") or 0)
    upcoming = int(totals.get("upcoming") or 0)

    # Saf Python — pandas olmadan branş oranları hesapla (event loop'u bloklamaz)
    by_specialty: list[SpecialtyStats] = []
    if specialty_rows:
        for row in specialty_rows:
            total = int(row.get("total") or 0)
            cancelled = int(row.get("cancelled") or 0)
            no_show = int(row.get("no_show") or 0)
            completed_sp = int(row.get("completed") or 0)
            by_specialty.append(SpecialtyStats(
                specialty=row.get("specialty"),
                total=total,
                cancelled=cancelled,
                no_show=no_show,
                completed=completed_sp,
                cancel_rate_pct=_safe_pct(cancelled, total),
                no_show_rate_pct=_safe_pct(no_show, total),
            ))

    response = AppointmentStatsResponse(
        period_start=start_date,
        period_end=end_date,
        total=total,
        cancelled=cancelled,
        no_show=no_show,
        completed=completed,
        upcoming=upcoming,
        cancel_rate_pct=_safe_pct(cancelled, total),
        no_show_rate_pct=_safe_pct(no_show, total),
        completion_rate_pct=_safe_pct(completed, total),
        by_specialty=by_specialty,
        cached=False,
    )
    await set_cache(cache_key, response.model_dump())
    return response


async def _fetch_raw(db, clinic_id, start_date, end_date, doctor_id=None):
    totals = await query_appointment_stats(db, clinic_id, start_date, end_date, doctor_id=doctor_id)
    specialty_rows = await query_appointments_by_specialty(db, clinic_id, start_date, end_date, doctor_id=doctor_id)
    return totals, specialty_rows
