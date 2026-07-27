"""
Hekim performans karnesi servisi.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import build_key, get_cache, set_cache
from app.queries import query_doctor_performance
from app.schemas import DoctorPerformanceResponse, DoctorScorecard


async def get_doctor_performance(
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> DoctorPerformanceResponse:
    cache_key = build_key("doctor_perf", clinic_id, start_date, end_date)
    cached = await get_cache(cache_key)
    if cached:
        cached.pop("cached", None)
        return DoctorPerformanceResponse(**cached, cached=True)

    rows = await query_doctor_performance(db, clinic_id, start_date, end_date)

    doctors = [
        DoctorScorecard(
            doctor_id=row["doctor_id"],
            doctor_name=row["doctor_name"],
            specialty=row.get("specialty"),
            total=int(row["total"]),
            completed=int(row["completed"]),
            cancelled=int(row["cancelled"]),
            no_show=int(row["no_show"]),
            cancel_rate_pct=float(row["cancel_rate_pct"]) if row.get("cancel_rate_pct") is not None else None,
            completion_rate_pct=float(row["completion_rate_pct"]) if row.get("completion_rate_pct") is not None else None,
            loyal_patient_count=int(row["loyal_patient_count"]),
        )
        for row in rows
    ]

    response = DoctorPerformanceResponse(
        period_start=start_date,
        period_end=end_date,
        doctors=doctors,
        cached=False,
    )
    await set_cache(cache_key, response.model_dump())
    return response
