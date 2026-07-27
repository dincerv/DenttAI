"""
Envanter israf raporu servisi.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import build_key, get_cache, set_cache
from app.queries import query_high_waste_materials, query_waste_by_category, query_expiring_cycles
from app.schemas import ExpiringCycle, ExpiringCyclesResponse, HighWasteMaterial, WasteCategorySummary, WasteReportResponse


async def get_waste_report(
    clinic_id: UUID,
    db: AsyncSession,
) -> WasteReportResponse:
    cache_key = build_key("waste_report", clinic_id)
    cached = await get_cache(cache_key)
    if cached:
        cached.pop("cached", None)
        return WasteReportResponse(**cached, cached=True)

    materials_raw = await query_high_waste_materials(db, clinic_id)
    category_raw = await query_waste_by_category(db, clinic_id)

    materials = [HighWasteMaterial(**row) for row in materials_raw]
    by_category = [
        WasteCategorySummary(
            category=row["category"],
            total_cycles=int(row["total_cycles"]),
            high_waste_count=int(row["high_waste_count"]),
            waste_rate_pct=float(row["waste_rate_pct"]) if row.get("waste_rate_pct") is not None else None,
            avg_actual_lifespan=float(row["avg_actual_lifespan"]) if row.get("avg_actual_lifespan") is not None else None,
            avg_expected_lifespan=float(row["avg_expected_lifespan"]) if row.get("avg_expected_lifespan") is not None else None,
        )
        for row in category_raw
    ]

    response = WasteReportResponse(
        total_high_waste=len(materials),
        by_category=by_category,
        materials=materials,
        cached=False,
    )
    await set_cache(cache_key, response.model_dump())
    return response


async def get_expiring_cycles(
    clinic_id: UUID,
    db: AsyncSession,
) -> ExpiringCyclesResponse:
    cache_key = build_key("expiring_cycles", clinic_id)
    cached = await get_cache(cache_key)
    if cached:
        cached.pop("cached", None)
        return ExpiringCyclesResponse(**cached, cached=True)

    rows = await query_expiring_cycles(db, clinic_id)
    items = [ExpiringCycle(**row) for row in rows]
    response = ExpiringCyclesResponse(items=items, cached=False)
    # Kısa cache: 15 dk (kritik bilgi, fazla stale olmasın)
    await set_cache(cache_key, response.model_dump(), ttl=900)
    return response
