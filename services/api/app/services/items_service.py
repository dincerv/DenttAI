"""
Envanter kalem (InventoryItem) CRUD servisi — Batch / Parti yönetimi destekli.
Tüm DB sorgularından önce set_rls_context çağrılmalıdır; bu sorumluluğu router taşır.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_item import InventoryItem
from app.models.inventory_adjustment import InventoryAdjustment
from app.schemas.items import AdjustQuantityRequest, ItemCreate, ItemUpdate


async def list_items(clinic_id: UUID, db: AsyncSession) -> list[InventoryItem]:
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.clinic_id == clinic_id)
        .order_by(InventoryItem.name, InventoryItem.expiry_date.asc().nulls_last())
    )
    return list(result.scalars().all())


async def get_item(item_id: UUID, clinic_id: UUID, db: AsyncSession) -> InventoryItem:
    item = await db.get(InventoryItem, item_id)
    if not item or item.clinic_id != clinic_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kalem bulunamadı")
    return item


async def _find_batch(
    name: str, clinic_id: UUID, expiry_date, batch_number: str | None, db: AsyncSession
) -> InventoryItem | None:
    """Composite key ile mevcut partiyi bul."""
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.name == name,
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.expiry_date == expiry_date,
            InventoryItem.batch_number == batch_number,
        )
    )
    return result.scalar_one_or_none()


async def create_item(data: ItemCreate, clinic_id: UUID, db: AsyncSession) -> InventoryItem:
    """
    Yeni parti oluşturur. Aynı (name + expiry_date + batch_number) composite key varsa
    mevcut partinin miktarını artırır (merge/upsert davranışı).
    Farklı SKT veya batch_number ile aynı isimli ürün yeni parti olarak eklenir.
    """
    # Önce aynı composite key ile mevcut parti var mı kontrol et
    existing = await _find_batch(data.name, clinic_id, data.expiry_date, data.batch_number, db)
    if existing:
        # Aynı parti zaten var → miktarı ekle (merge)
        existing.quantity = existing.quantity + Decimal(str(data.quantity))
        # Diğer alanları da güncelle (cost, min_stock vb.)
        if data.cost_per_unit is not None:
            existing.cost_per_unit = Decimal(str(data.cost_per_unit))
        if data.min_stock_level:
            existing.min_stock_level = Decimal(str(data.min_stock_level))
        if data.category:
            existing.category = data.category
        if data.shelf_code:
            existing.shelf_code = data.shelf_code
        await db.commit()
        await db.refresh(existing)
        return existing

    try:
        item = InventoryItem(clinic_id=clinic_id, **data.model_dump())
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item
    except IntegrityError:
        await db.rollback()
        # Race condition durumunda tekrar merge dene
        existing = await _find_batch(data.name, clinic_id, data.expiry_date, data.batch_number, db)
        if existing:
            existing.quantity = existing.quantity + Decimal(str(data.quantity))
            await db.commit()
            await db.refresh(existing)
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu parti (name + SKT + batch_number) zaten mevcut",
        )


async def update_item(
    item_id: UUID, data: ItemUpdate, clinic_id: UUID, db: AsyncSession
) -> InventoryItem:
    item = await get_item(item_id, clinic_id, db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(item_id: UUID, clinic_id: UUID, db: AsyncSession) -> None:
    item = await get_item(item_id, clinic_id, db)
    await db.delete(item)
    await db.commit()


async def adjust_quantity(
    item_id: UUID,
    req: AdjustQuantityRequest,
    clinic_id: UUID,
    db: AsyncSession,
    performed_by: UUID | None = None,
    performed_by_email: str | None = None,
) -> InventoryItem:
    """Belirli bir partinin (batch) miktarını ayarlar."""
    item = await get_item(item_id, clinic_id, db)
    new_qty = item.quantity + Decimal(str(req.delta))
    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stok sıfırın altına düşemez (mevcut: {item.quantity}, delta: {req.delta})",
        )
    item.quantity = new_qty
    adj = InventoryAdjustment(
        clinic_id=clinic_id,
        item_id=item_id,
        delta=req.delta,
        reason=req.reason,
        performed_by=performed_by,
        performed_by_email=performed_by_email,
    )
    db.add(adj)
    await db.commit()
    await db.refresh(item)
    return item


async def list_adjustments(
    item_id: UUID, clinic_id: UUID, db: AsyncSession
) -> list[InventoryAdjustment]:
    result = await db.execute(
        select(InventoryAdjustment)
        .where(
            InventoryAdjustment.item_id == item_id,
            InventoryAdjustment.clinic_id == clinic_id,
        )
        .order_by(InventoryAdjustment.created_at.desc())
    )
    return list(result.scalars().all())
