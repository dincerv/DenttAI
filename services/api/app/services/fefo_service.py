"""
FEFO (First Expired, First Out) Servis Modülü.

Stateless ve modüler: Tüm logic saf fonksiyonlardan oluşur.
İleride bağımsız bir Analytics Engine'e taşınabilir.

Sorumluluklar:
  - Aynı isimdeki ürün partilerini toplar, toplam miktarı hesaplar
  - Son kullanma uyarısını vadesi en yakın olan partiye göre tetikler
  - Stok düşümünde FEFO sırasıyla hangi partiden düşüleceğini hesaplar
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_item import InventoryItem
from app.schemas.items import BatchInfo, BatchSummary


def _days_until(expiry: date | None) -> int | None:
    """Son kullanma tarihine kaç gün kaldığını hesaplar."""
    if expiry is None:
        return None
    return (expiry - date.today()).days


async def get_batch_summaries(
    clinic_id: UUID,
    db: AsyncSession,
) -> list[BatchSummary]:
    """
    Kliniğin tüm envanterini ürün adına göre gruplar.
    Her grup için toplam miktar, toplam min_stock ve FEFO sıralı parti listesi döner.
    """
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.clinic_id == clinic_id)
        .order_by(InventoryItem.name, InventoryItem.expiry_date.asc().nulls_last())
    )
    items = list(result.scalars().all())

    groups: dict[str, list[InventoryItem]] = {}
    for item in items:
        groups.setdefault(item.name, []).append(item)

    summaries: list[BatchSummary] = []
    for name, batches in groups.items():
        total_qty = sum(float(b.quantity) for b in batches)
        # min_stock_level ürün bazlı bir eşiktir, parti bazlı değil.
        # Tüm partilerdeki en yüksek değeri al (hepsi aynı olmalı, ama güvenlik için max).
        total_min = max(float(b.min_stock_level) for b in batches)

        # FEFO: vadesi en yakın olan parti önce
        dated = [b for b in batches if b.expiry_date is not None]
        dated.sort(key=lambda b: b.expiry_date)  # type: ignore[arg-type]
        nearest = dated[0].expiry_date if dated else None

        batch_infos = [
            BatchInfo(
                batch_id=b.id,
                batch_number=b.batch_number,
                quantity=float(b.quantity),
                expiry_date=b.expiry_date,
                days_until_expiry=_days_until(b.expiry_date),
                is_low_stock=b.is_low_stock,
            )
            for b in batches
        ]

        first = batches[0]
        summaries.append(
            BatchSummary(
                name=name,
                category=first.category,
                unit=first.unit,
                total_quantity=total_qty,
                total_min_stock=total_min,
                is_low_stock=total_qty <= total_min,
                nearest_expiry_date=nearest,
                days_until_nearest_expiry=_days_until(nearest),
                batches=batch_infos,
            )
        )

    return summaries


def compute_fefo_deduction(
    batches: list[BatchInfo],
    amount: float,
) -> list[tuple[UUID, float]]:
    """
    Verilen miktarı FEFO sırasıyla partilerden düşer.
    Dönen liste: [(batch_id, düşüm_miktarı), ...]

    Saf fonksiyon — side-effect yok, DB'ye dokunmaz.
    Analytics Engine'e taşınmak için hazır.
    """
    remaining = amount
    deductions: list[tuple[UUID, float]] = []

    # FEFO: expiry_date en yakın olan önce; None en sona
    sorted_batches = sorted(
        batches,
        key=lambda b: b.expiry_date if b.expiry_date is not None else date.max,
    )

    for batch in sorted_batches:
        if remaining <= 0:
            break
        take = min(batch.quantity, remaining)
        if take > 0:
            deductions.append((batch.batch_id, take))
            remaining -= take

    return deductions
