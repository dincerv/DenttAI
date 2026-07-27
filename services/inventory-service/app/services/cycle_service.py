"""
Döngü (Cycle) Servisi: Döngü kapatma ve anomali tespiti.

Anomali kuralı:
  actual_lifespan < expected_lifespan * ANOMALY_THRESHOLD_RATIO  → is_high_waste = True

actual_lifespan DB'de GENERATED ALWAYS AS (end_date - start_date) ile hesaplanır.
Commit sonrasında refresh ile güncel değer okunur.
"""
from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cycle_material import CycleMaterial
from app.schemas.cycle import CycleEndRequest, CycleEndResponse, CycleMaterialResponse


async def end_cycle(
    req: CycleEndRequest, clinic_id: UUID, db: AsyncSession
) -> CycleEndResponse:
    result = await db.execute(
        select(CycleMaterial).where(
            CycleMaterial.qr_id == req.qr_id,
            CycleMaterial.clinic_id == clinic_id,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR bulunamadı")
    if not material.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Malzeme zaten pasif; döngü zaten kapatılmış",
        )

    today = datetime.date.today()
    material.end_date = today
    material.is_active = False
    material.end_reason = req.end_reason
    material.waste_note = req.waste_note

    # Anomali tespiti (DB GENERATED sütunu commit sonrası refresh ile güncellenir)
    # Ancak DB refresh'ten önce de uygulama katmanında hesaplayabiliriz
    actual: int | None = None
    anomaly_message: str | None = None
    if material.start_date:
        actual = (today - material.start_date).days
        if material.expected_lifespan and actual < material.expected_lifespan * settings.ANOMALY_THRESHOLD_RATIO:
            material.is_high_waste = True
            anomaly_message = (
                f"YÜKSEK İSRAF: Beklenen ömür {material.expected_lifespan} gün, "
                f"gerçekleşen {actual} gün "
                f"(%{settings.ANOMALY_THRESHOLD_RATIO * 100:.0f} eşiğinin altında)"
            )

    await db.commit()
    await db.refresh(material)

    return CycleEndResponse(
        material_id=material.id,
        qr_id=material.qr_id,
        name=material.name,
        start_date=material.start_date,
        end_date=material.end_date,
        expected_lifespan=material.expected_lifespan,
        actual_lifespan=material.actual_lifespan if material.actual_lifespan is not None else actual,
        is_high_waste=material.is_high_waste,
        end_reason=material.end_reason,
        waste_note=material.waste_note,
        anomaly_message=anomaly_message,
    )


async def list_cycles(
    clinic_id: UUID,
    db: AsyncSession,
    only_active: bool = False,
    only_waste: bool = False,
) -> list[CycleMaterialResponse]:
    query = select(CycleMaterial).where(CycleMaterial.clinic_id == clinic_id)
    if only_active:
        query = query.where(CycleMaterial.is_active == True)  # noqa: E712
    if only_waste:
        query = query.where(CycleMaterial.is_high_waste == True)  # noqa: E712
    query = query.order_by(CycleMaterial.created_at.desc())
    result = await db.execute(query)
    return [CycleMaterialResponse.model_validate(m) for m in result.scalars().all()]
