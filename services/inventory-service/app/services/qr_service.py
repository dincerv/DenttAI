"""
QR Servisi: Malzeme oluşturma + QR üretme + QR aktivasyonu.
Batch (Parti) bazlı QR kod üretimi — her yeni stok girişi benzersiz bir QR alır.
qrcode[pil] library PNG → BytesIO → base64.
"""
from __future__ import annotations

import base64
import io
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import random
import string

import qrcode
from qrcode.image.pil import PilImage

from app.models.cycle_material import CycleMaterial
from app.models.inventory_item import InventoryItem
from app.schemas.qr import QRActivateResponse, QRGenerateRequest, QRGenerateResponse

import datetime

_CHARS = string.ascii_uppercase + string.digits


def _make_shelf_code() -> str:
    """3 harf + 3 rakam formatında kısa, okunabilir raf kodu üretir. Örn: KRT-847"""
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    digits  = ''.join(random.choices(string.digits, k=3))
    return f"{letters}-{digits}"


def _make_qr_image_base64(data: str) -> str:
    """Verilen string için QR PNG üretir; base64 döndürür."""
    img: PilImage = qrcode.make(data)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def generate_batch_qr_data(item_id: UUID) -> tuple[str, str]:
    """
    Envanter partisi için benzersiz QR verisi ve base64 PNG üretir.
    Dönen: (qr_data_string, qr_png_base64)
    """
    qr_data = f"BATCH:{item_id}"
    return qr_data, _make_qr_image_base64(qr_data)


async def generate_qr(
    req: QRGenerateRequest, clinic_id: UUID, db: AsyncSession
) -> QRGenerateResponse:
    qr_id = str(uuid4())
    shelf_code = _make_shelf_code()
    material = CycleMaterial(
        clinic_id=clinic_id,
        qr_id=qr_id,
        shelf_code=shelf_code,
        name=req.name,
        category=req.category,
        expected_lifespan=req.expected_lifespan,
        is_active=False,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    qr_code_b64 = _make_qr_image_base64(qr_id)
    return QRGenerateResponse(
        qr_id=qr_id,
        shelf_code=shelf_code,
        material_id=material.id,
        qr_code_base64=qr_code_b64,
    )


async def activate_qr(
    qr_id: str, clinic_id: UUID, db: AsyncSession
) -> QRActivateResponse:
    result = await db.execute(
        select(CycleMaterial).where(
            CycleMaterial.qr_id == qr_id,
            CycleMaterial.clinic_id == clinic_id,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR bulunamadı")
    if material.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Malzeme zaten aktif; tekrar aktive edilemez",
        )

    material.start_date = datetime.date.today()
    material.activated_at = datetime.datetime.now(datetime.timezone.utc)
    material.is_active = True
    await db.commit()
    await db.refresh(material)

    return QRActivateResponse(qr_id=qr_id, material_id=material.id)
