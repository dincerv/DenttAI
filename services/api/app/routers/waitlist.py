"""
Waitlist Router — /waitlist
Branş bazlı yedek liste yönetimi.
Multi-tenancy: her endpoint'te RLS context set edilir.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.waitlist import (
    WaitlistAddRequest,
    WaitlistResponse,
    WaitlistUpdateRequest,
)
from app.services.waitlist_engine import (
    add_to_waitlist,
    list_waitlist,
    remove_from_waitlist,
    update_waitlist_entry,
)
from shared.auth_middleware import get_verified_claims, require_role, set_rls_context

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


@router.post(
    "",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yedek listeye hasta ekle",
)
async def add(
    data: WaitlistAddRequest,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    await set_rls_context(db, claims["clinic_id"])
    return await add_to_waitlist(data, claims["clinic_id"], db)


@router.get(
    "",
    response_model=list[WaitlistResponse],
    summary="Yedek listeyi getir (öncelik sıralı)",
)
async def list_all(
    specialty: str | None = Query(default=None, description="Branş filtresi"),
    active_only: bool = Query(default=True, description="Yalnızca aktif kayıtlar"),
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> list[WaitlistResponse]:
    await set_rls_context(db, claims["clinic_id"])
    return await list_waitlist(claims["clinic_id"], db, specialty, active_only)


@router.patch(
    "/{entry_id}",
    response_model=WaitlistResponse,
    summary="Yedek liste kaydını güncelle (öncelik, aktiflik)",
)
async def update(
    entry_id: UUID,
    data: WaitlistUpdateRequest,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    await set_rls_context(db, claims["clinic_id"])
    return await update_waitlist_entry(entry_id, claims["clinic_id"], data, db)


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Yedek listeden çıkar (soft delete)",
    dependencies=[Depends(require_role("owner", "doctor", "assistant"))],
    response_class=Response,
)
async def remove(
    entry_id: UUID,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await set_rls_context(db, claims["clinic_id"])
    await remove_from_waitlist(entry_id, claims["clinic_id"], db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
