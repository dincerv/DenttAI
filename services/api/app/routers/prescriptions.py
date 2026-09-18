"""Prescription router — /prescriptions"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.prescription import (
    PrescriptionCreate,
    PrescriptionListResponse,
    PrescriptionResponse,
    PrescriptionSummaryResponse,
)
from app.services.prescription_service import (
    cancel_prescription,
    create_prescription,
    get_prescription,
    get_summary,
    issue_prescription,
    list_prescriptions,
)
from shared.auth_middleware import (
    get_verified_claims,
    require_role,
    set_rls_context,
)

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


async def require_prescription_view(claims: dict = Depends(get_verified_claims)) -> dict:
    role = claims.get("role")
    if role in ("super_admin", "owner", "doctor"):
        return claims
    allowed = claims.get("allowed_pages") or []
    if "prescriptions" in allowed:
        return claims
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bu işlem için 'prescriptions' yetkisi gerekiyor",
    )


@router.get("/summary", response_model=PrescriptionSummaryResponse)
async def prescription_summary(
    claims: dict = Depends(require_prescription_view),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await get_summary(db, claims["clinic_id"])


@router.get("", response_model=PrescriptionListResponse)
async def list_prescriptions_endpoint(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    claims: dict = Depends(require_prescription_view),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await list_prescriptions(
        db, claims["clinic_id"],
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/{rx_id}", response_model=PrescriptionResponse)
async def get_prescription_endpoint(
    rx_id: UUID,
    claims: dict = Depends(require_prescription_view),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await get_prescription(db, rx_id)


@router.post("", response_model=PrescriptionResponse, status_code=201)
async def create_prescription_endpoint(
    body: PrescriptionCreate,
    claims: dict = Depends(require_role("owner", "doctor", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await create_prescription(
        db, claims["clinic_id"], body, claims["user_id"], claims["role"],
    )


@router.post("/{rx_id}/issue", response_model=PrescriptionResponse)
async def issue_prescription_endpoint(
    rx_id: UUID,
    claims: dict = Depends(require_role("owner", "doctor", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await issue_prescription(db, claims["clinic_id"], rx_id)


@router.post("/{rx_id}/cancel", response_model=PrescriptionResponse)
async def cancel_prescription_endpoint(
    rx_id: UUID,
    claims: dict = Depends(require_role("owner", "doctor", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await cancel_prescription(db, rx_id)
