"""
Tedavi sayaçları servisi.

Randevu notlarını (free-text) parse ederek:
  Dolgu / Kanal / İmplant / Kron / Çekim / Protez / Ortodonti / Temizlik
sayılarını dönem bazlı (Günlük/Haftalık/Aylık/Yıllık) özetler.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import build_key, get_cache, set_cache
from app.queries import query_treatment_counts, query_treatment_totals, query_treatments_by_doctor
from app.schemas import (
    TreatmentCountsResponse, TreatmentPeriod, TreatmentTotals,
    DoctorTreatmentRow, TreatmentsByDoctorResponse,
)

_CACHE_TTL = 600  # 10 dakika (tedavi verileri sık değişmez)


async def get_treatment_counts(
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession,
    doctor_id: UUID | None = None,
    doctor_name: str | None = None,
    group_by: str = "month",
) -> TreatmentCountsResponse:
    cache_key = build_key(
        "treatment_counts", clinic_id,
        str(doctor_id or "all"), start_date, end_date, group_by,
    )
    cached = await get_cache(cache_key)
    if cached:
        cached.pop("cached", None)
        return TreatmentCountsResponse(**cached, cached=True)

    trend_rows = await query_treatment_counts(
        db, clinic_id, start_date, end_date,
        doctor_id=doctor_id, group_by=group_by,
    )
    totals_row = await query_treatment_totals(
        db, clinic_id, start_date, end_date, doctor_id=doctor_id,
    )

    def _int(v) -> int:
        return int(v) if v is not None else 0

    totals = TreatmentTotals(
        total_completed=_int(totals_row.get("total_completed")),
        dolgu=_int(totals_row.get("dolgu")),
        kanal=_int(totals_row.get("kanal")),
        implant=_int(totals_row.get("implant")),
        kron=_int(totals_row.get("kron")),
        cekim=_int(totals_row.get("cekim")),
        protez=_int(totals_row.get("protez")),
        ortodonti=_int(totals_row.get("ortodonti")),
        temizlik=_int(totals_row.get("temizlik")),
    )

    trend = [
        TreatmentPeriod(
            period=row["period"],
            total_completed=_int(row.get("total_completed")),
            dolgu=_int(row.get("dolgu")),
            kanal=_int(row.get("kanal")),
            implant=_int(row.get("implant")),
            kron=_int(row.get("kron")),
            cekim=_int(row.get("cekim")),
            protez=_int(row.get("protez")),
            ortodonti=_int(row.get("ortodonti")),
            temizlik=_int(row.get("temizlik")),
            beyazlatma=_int(row.get("beyazlatma")),
        )
        for row in trend_rows
    ]

    response = TreatmentCountsResponse(
        period_start=start_date,
        period_end=end_date,
        group_by=group_by,
        doctor_id=doctor_id,
        doctor_name=doctor_name,
        totals=totals,
        trend=trend,
        cached=False,
    )
    await set_cache(cache_key, response.model_dump(), ttl=_CACHE_TTL)
    return response


async def get_treatments_by_doctor(
    clinic_id: UUID,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> TreatmentsByDoctorResponse:
    cache_key = build_key("treatments_by_doctor", clinic_id, start_date, end_date)
    cached = await get_cache(cache_key)
    if cached:
        cached.pop("cached", None)
        return TreatmentsByDoctorResponse(**cached, cached=True)

    rows = await query_treatments_by_doctor(db, clinic_id, start_date, end_date)

    def _int(v) -> int:
        return int(v) if v is not None else 0

    doctors = [
        DoctorTreatmentRow(
            doctor_id=row["doctor_id"],
            doctor_name=row["doctor_name"],
            specialty=row.get("specialty"),
            total_completed=_int(row.get("total_completed")),
            dolgu=_int(row.get("dolgu")),
            kanal=_int(row.get("kanal")),
            implant=_int(row.get("implant")),
            kron=_int(row.get("kron")),
            cekim=_int(row.get("cekim")),
            protez=_int(row.get("protez")),
            ortodonti=_int(row.get("ortodonti")),
            temizlik=_int(row.get("temizlik")),
        )
        for row in rows
    ]

    response = TreatmentsByDoctorResponse(
        period_start=start_date,
        period_end=end_date,
        doctors=doctors,
        cached=False,
    )
    await set_cache(cache_key, response.model_dump(), ttl=_CACHE_TTL)
    return response
