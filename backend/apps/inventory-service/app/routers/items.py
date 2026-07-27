"""Router: Envanter kalemleri — CRUD + stok ayarlama + batch (parti) özeti."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.items import (
    AdjustQuantityRequest, AdjustmentResponse, BatchSummary,
    ItemCreate, ItemResponse, ItemUpdate,
)
from app.services import (
    adjust_quantity, create_item, delete_item, get_batch_summaries,
    get_item, list_adjustments, list_items, update_item,
)
from shared.auth_middleware import get_verified_claims, set_rls_context, require_role

router = APIRouter(prefix="/inventory/items", tags=["inventory-items"])


@router.get("/batches", response_model=list[BatchSummary])
async def read_batch_summaries(
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    """
    Tüm envanterin ürün adına göre gruplandırılmış parti özetini döner.
    FEFO (First Expired, First Out) sıralı batch bilgisi içerir.
    """
    await set_rls_context(db, claims["clinic_id"])
    return await get_batch_summaries(clinic_id=claims["clinic_id"], db=db)


@router.get("", response_model=list[ItemResponse])
async def read_items(
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await list_items(clinic_id=claims["clinic_id"], db=db)


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_new_item(
    body: ItemCreate,
    claims: dict = Depends(require_role("owner", "doctor", "assistant")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await create_item(data=body, clinic_id=claims["clinic_id"], db=db)


@router.get("/{item_id}", response_model=ItemResponse)
async def read_item(
    item_id: UUID,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await get_item(item_id=item_id, clinic_id=claims["clinic_id"], db=db)


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_existing_item(
    item_id: UUID,
    body: ItemUpdate,
    claims: dict = Depends(require_role("owner", "doctor", "assistant")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await update_item(item_id=item_id, data=body, clinic_id=claims["clinic_id"], db=db)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_item(
    item_id: UUID,
    claims: dict = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    await delete_item(item_id=item_id, clinic_id=claims["clinic_id"], db=db)


@router.post("/{item_id}/adjust", response_model=ItemResponse)
async def adjust_item_quantity(
    item_id: UUID,
    body: AdjustQuantityRequest,
    claims: dict = Depends(require_role("owner", "doctor", "assistant")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await adjust_quantity(
        item_id=item_id,
        req=body,
        clinic_id=claims["clinic_id"],
        db=db,
        performed_by=claims.get("sub"),
        performed_by_email=claims.get("email"),
    )


@router.get("/{item_id}/history", response_model=list[AdjustmentResponse])
async def get_item_history(
    item_id: UUID,
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await list_adjustments(item_id=item_id, clinic_id=claims["clinic_id"], db=db)
