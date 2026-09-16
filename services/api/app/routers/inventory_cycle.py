"""Router: Döngü yönetimi — listeleme + döngü kapatma."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.cycle import CycleEndRequest, CycleEndResponse, CycleMaterialResponse
from app.services import end_cycle, list_cycles
from shared.auth_middleware import get_verified_claims, require_role, set_rls_context

router = APIRouter(prefix="/inventory/cycle", tags=["inventory-cycle"])


@router.get("", response_model=list[CycleMaterialResponse])
async def read_cycles(
    only_active: bool = Query(False, description="Sadece aktif malzemeleri getir"),
    only_waste: bool = Query(False, description="Sadece yüksek israf kayıtları"),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    """Kliniğin tüm döngüsel malzeme kayıtlarını getirir."""
    await set_rls_context(db, claims["clinic_id"])
    return await list_cycles(
        clinic_id=claims["clinic_id"],
        db=db,
        only_active=only_active,
        only_waste=only_waste,
    )


@router.post("/end", response_model=CycleEndResponse)
async def close_cycle(
    body: CycleEndRequest,
    claims: dict = Depends(require_role("owner", "doctor", "assistant")),
    db: AsyncSession = Depends(get_db),
):
    """
    Malzemenin kullanım döngüsünü kapatır.
    Anomali tespiti: actual_lifespan < expected_lifespan * 0.25 → is_high_waste = True.
    """
    await set_rls_context(db, claims["clinic_id"])
    return await end_cycle(req=body, clinic_id=claims["clinic_id"], db=db)
