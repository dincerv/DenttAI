"""Dental chart + treatment plan — /dental"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.dental import (
    ChartResponse,
    ToothState,
    ToothUpsert,
    TreatmentComplete,
    TreatmentCreate,
    TreatmentListResponse,
    TreatmentResponse,
    TreatmentUpdate,
)
from app.services.dental_chart_service import (
    cancel_treatment,
    complete_treatment,
    create_treatment,
    get_chart,
    list_treatments,
    update_treatment,
    upsert_tooth,
)
from shared.auth_middleware import (
    require_page_permission,
    set_rls_context,
)

router = APIRouter(prefix="/dental", tags=["Dental"])


@router.get("/patients/{patient_id}/chart", response_model=ChartResponse)
async def chart(
    patient_id: UUID,
    claims: dict = Depends(require_page_permission("patients")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await get_chart(db, claims["clinic_id"], patient_id)


@router.put("/patients/{patient_id}/teeth/{tooth_fdi}", response_model=ToothState)
async def set_tooth(
    patient_id: UUID,
    tooth_fdi: int,
    body: ToothUpsert,
    claims: dict = Depends(require_page_permission("patients")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await upsert_tooth(
        db, claims["clinic_id"], patient_id, tooth_fdi, body, claims["user_id"]
    )


@router.get("/patients/{patient_id}/treatments", response_model=TreatmentListResponse)
async def treatments(
    patient_id: UUID,
    claims: dict = Depends(require_page_permission("patients")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await list_treatments(db, claims["clinic_id"], patient_id)


@router.post(
    "/patients/{patient_id}/treatments",
    response_model=TreatmentResponse,
    status_code=201,
)
async def add_treatment(
    patient_id: UUID,
    body: TreatmentCreate,
    claims: dict = Depends(require_page_permission("patients")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await create_treatment(
        db, claims["clinic_id"], patient_id, body, claims["user_id"], claims["role"]
    )


@router.patch("/treatments/{treatment_id}", response_model=TreatmentResponse)
async def patch_treatment(
    treatment_id: UUID,
    body: TreatmentUpdate,
    claims: dict = Depends(require_page_permission("patients")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await update_treatment(db, claims["clinic_id"], treatment_id, body)


@router.post("/treatments/{treatment_id}/complete", response_model=TreatmentResponse)
async def finish_treatment(
    treatment_id: UUID,
    body: TreatmentComplete,
    claims: dict = Depends(require_page_permission("patients")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await complete_treatment(
        db, claims["clinic_id"], treatment_id, body, claims["user_id"]
    )


@router.post("/treatments/{treatment_id}/cancel", response_model=TreatmentResponse)
async def stop_treatment(
    treatment_id: UUID,
    claims: dict = Depends(require_page_permission("patients")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await cancel_treatment(db, claims["clinic_id"], treatment_id)
