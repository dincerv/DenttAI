"""
Analytics routers — RBAC uygulamalı.

Yetki Matrisi:
  super_admin  — Tüm endpoint'ler, isteğe bağlı ?target_clinic_id ile klinik geçersiz kılma
  owner        — Klinik geneli tüm data
  doctor       — Sadece kendi randevu/tedavi verileri (doctor_id filtrelemesi)
  assistant    — Sadece envanter endpoint'leri; ciro/performans → 403
"""
from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import (
    AIChatRequest,
    AIChatResponse,
    AppointmentStatsResponse,
    DoctorPerformanceResponse,
    ExpiringCyclesResponse,
    NewPatientsOverviewResponse,
    RecoveredRevenueResponse,
    TreatmentCountsResponse,
    TreatmentsByDoctorResponse,
    WasteReportResponse,
)
from app.services import (
    answer_clinic_question,
    get_appointment_stats,
    get_doctor_performance,
    get_expiring_cycles,
    get_recovered_revenue,
    get_treatment_counts,
    get_treatments_by_doctor,
    get_waste_report,
)
from shared.auth_middleware import get_verified_claims, set_rls_context

_FINANCE_BLOCKED = ("assistant",)
_PERF_BLOCKED    = ("assistant",)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _default_period() -> tuple[datetime.date, datetime.date]:
    today = datetime.date.today()
    return today.replace(day=1), today


def _resolve_period(
    start: datetime.date | None,
    end: datetime.date | None,
) -> tuple[datetime.date, datetime.date]:
    default_start, default_end = _default_period()
    return start or default_start, end or default_end


async def _setup(claims: dict, db: AsyncSession, target_clinic_id: UUID | None = None) -> UUID:
    """RLS context'ini ayarla. super_admin target_clinic_id ile override edebilir."""
    clinic_id = target_clinic_id if (target_clinic_id and claims["role"] == "super_admin") else claims["clinic_id"]
    await set_rls_context(db, clinic_id)
    return clinic_id


# ── Recovered Revenue ──────────────────────────────────────────────────────

@router.get("/revenue/recovered", response_model=RecoveredRevenueResponse)
async def recovered_revenue(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    if claims["role"] in _FINANCE_BLOCKED or claims["role"] == "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Finansal verilere erişim yetkiniz bulunmuyor")
    start, end = _resolve_period(start_date, end_date)
    clinic_id = await _setup(claims, db, target_clinic_id)
    return await get_recovered_revenue(clinic_id=clinic_id, start_date=start, end_date=end, db=db)


# ── Appointment Stats ──────────────────────────────────────────────────────

@router.get("/appointments/stats", response_model=AppointmentStatsResponse)
async def appointment_stats(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    if claims["role"] in _FINANCE_BLOCKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="İstatistik verilerine erişim yetkiniz bulunmuyor")
    start, end = _resolve_period(start_date, end_date)
    clinic_id = await _setup(claims, db, target_clinic_id)
    if claims["role"] == "doctor":
        doctor_id = claims.get("doctor_id")
        if not doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Doktor kaydı henüz eşleştirilmemiş, lütfen yöneticinizle iletişime geçin")
    else:
        doctor_id = None
    return await get_appointment_stats(
        clinic_id=clinic_id, start_date=start, end_date=end, db=db, doctor_id=doctor_id,
    )


@router.get("/patients/new-overview", response_model=NewPatientsOverviewResponse)
async def new_patients_overview(
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    """Yeni hasta sayıları: bugün / bu hafta / bu ay / bu yıl."""
    if claims["role"] not in ("owner", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu rapora erişim yetkiniz bulunmuyor",
        )

    clinic_id = await _setup(claims, db, target_clinic_id)
    row = (
        await db.execute(
            sa_text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('day', NOW())   AND is_new_patient = TRUE)  AS day_new,
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('day', NOW())   AND is_new_patient = FALSE) AS day_old,
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('week', NOW())  AND is_new_patient = TRUE)  AS week_new,
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('week', NOW())  AND is_new_patient = FALSE) AS week_old,
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('month', NOW()) AND is_new_patient = TRUE)  AS month_new,
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('month', NOW()) AND is_new_patient = FALSE) AS month_old,
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('year', NOW())  AND is_new_patient = TRUE)  AS year_new,
                    COUNT(*) FILTER (WHERE scheduled_at >= date_trunc('year', NOW())  AND is_new_patient = FALSE) AS year_old
                FROM appointments
                WHERE clinic_id = :clinic_id
                  AND status <> 'cancelled'
                """
            ),
            {"clinic_id": str(clinic_id)},
        )
    ).mappings().first() or {}

    return NewPatientsOverviewResponse(
        day={"new_count": int(row.get("day_new") or 0), "old_count": int(row.get("day_old") or 0)},
        week={"new_count": int(row.get("week_new") or 0), "old_count": int(row.get("week_old") or 0)},
        month={"new_count": int(row.get("month_new") or 0), "old_count": int(row.get("month_old") or 0)},
        year={"new_count": int(row.get("year_new") or 0), "old_count": int(row.get("year_old") or 0)},
        generated_at=datetime.datetime.utcnow(),
    )


# ── Inventory Waste Report ─────────────────────────────────────────────────

@router.get("/inventory/waste-report", response_model=WasteReportResponse)
async def waste_report(
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = await _setup(claims, db, target_clinic_id)
    return await get_waste_report(clinic_id=clinic_id, db=db)


# ── Doctor Performance ─────────────────────────────────────────────────────

@router.get("/doctors/performance", response_model=DoctorPerformanceResponse)
async def doctor_performance(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    if claims["role"] in _PERF_BLOCKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Hekim performans verilerine erişim yetkiniz bulunmuyor")
    start, end = _resolve_period(start_date, end_date)
    clinic_id = await _setup(claims, db, target_clinic_id)
    perf = await get_doctor_performance(
        clinic_id=clinic_id, start_date=start, end_date=end, db=db
    )
    if claims["role"] == "doctor" and claims.get("doctor_id"):
        perf.doctors = [d for d in perf.doctors if d.doctor_id == claims["doctor_id"]]
    return perf


# ── Treatment Counts (Tedavi Sayaçları) ───────────────────────────────────

@router.get("/treatments/counts", response_model=TreatmentCountsResponse)
async def treatment_counts(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    group_by: str = Query("month", description="day | week | month | year"),
    doctor_id_filter: UUID | None = Query(None, alias="doctor_id"),
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    if claims["role"] in _PERF_BLOCKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Tedavi istatistiklerine erişim yetkiniz bulunmuyor")
    start, end = _resolve_period(start_date, end_date)
    clinic_id = await _setup(claims, db, target_clinic_id)
    if claims["role"] == "doctor":
        eff_doctor_id = claims.get("doctor_id")
        if not eff_doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Doktor kaydı henüz eşleştirilmemiş, lütfen yöneticinizle iletişime geçin")
        eff_doctor_name = claims.get("full_name")
    else:
        eff_doctor_id = doctor_id_filter
        eff_doctor_name = None
    return await get_treatment_counts(
        clinic_id=clinic_id, start_date=start, end_date=end, db=db,
        doctor_id=eff_doctor_id, doctor_name=eff_doctor_name, group_by=group_by,
    )


# ── Treatments By Doctor (Sahip görünümü) ─────────────────────────────────

@router.get("/treatments/by-doctor", response_model=TreatmentsByDoctorResponse)
async def treatments_by_doctor(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    """Her hekim için tedavi türü bazlı sayılar. Sadece owner ve super_admin erişebilir."""
    if claims["role"] not in ("owner", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Bu rapora erişim yetkiniz bulunmuyor")
    start, end = _resolve_period(start_date, end_date)
    clinic_id = await _setup(claims, db, target_clinic_id)
    return await get_treatments_by_doctor(
        clinic_id=clinic_id, start_date=start, end_date=end, db=db,
    )


# ── Expiring Cycles ───────────────────────────────────────────────────────

@router.get("/inventory/expiring-cycles", response_model=ExpiringCyclesResponse)
async def expiring_cycles(
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = await _setup(claims, db, target_clinic_id)
    return await get_expiring_cycles(clinic_id=clinic_id, db=db)


@router.post("/ai/chat", response_model=AIChatResponse)
async def ai_chat(
    body: AIChatRequest,
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    """Klinik sahibinin/superadmin'in veriye dayali analiz sorularini yanitlar."""
    if claims["role"] not in ("owner", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI analiz yardimcisi yalnizca klinik sahipleri ve super_admin icin acik",
        )

    clinic_id = await _setup(claims, db, target_clinic_id)
    answer, model, fallback_used, usage = await answer_clinic_question(body.message, db)

    if not fallback_used and usage["total_tokens"] > 0:
        await db.execute(
            sa_text(
                """
                INSERT INTO ai_usage_events (
                    clinic_id,
                    source_service,
                    feature_key,
                    provider,
                    model_name,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost_usd,
                    metadata
                )
                VALUES (
                    :clinic_id,
                    :source_service,
                    :feature_key,
                    :provider,
                    :model_name,
                    :prompt_tokens,
                    :completion_tokens,
                    :total_tokens,
                    :cost_usd,
                    :metadata::jsonb
                )
                """
            ),
            {
                "clinic_id": str(clinic_id),
                "source_service": "analytics-service",
                "feature_key": "ai_chat",
                "provider": "gemini" if "gemini" in model.lower() else "openai",
                "model_name": model,
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
                "cost_usd": usage["cost_usd"],
                "metadata": '{"source":"dashboard_ai_chat"}',
            },
        )
        await db.commit()

    return AIChatResponse(answer=answer, model=model, fallback_used=fallback_used)


# ── AI Proaktif İçgörüler ─────────────────────────────────────────────────────

@router.get("/ai/insights")
async def ai_insights(
    target_clinic_id: UUID | None = Query(None),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    """
    Klinik sahibine yönelik proaktif AI içgörü kartları.

    Son 30 günlük verileri analiz ederek randevu, envanter, hasta şikayeti ve
    performans hakkında eyleme dönüştürülebilir öneriler üretir.
    Yalnızca owner ve super_admin rolü erişebilir.
    """
    if claims["role"] not in ("owner", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI içgörüleri yalnızca klinik sahipleri ve super_admin için açık",
        )

    clinic_id = await _setup(claims, db, target_clinic_id)

    from app.services.insights_service import generate_clinic_insights
    result = await generate_clinic_insights(clinic_id=clinic_id, db=db)
    return result
