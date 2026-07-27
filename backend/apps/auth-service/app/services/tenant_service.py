"""
Tenant iş mantığı: klinik bilgisi okuma ve güncelleme
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic
from app.schemas.tenant import ClinicResponse, ClinicUpdateRequest


async def get_clinic(clinic_id: uuid.UUID, db: AsyncSession) -> ClinicResponse:
    await db.execute(
        text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(clinic_id)),
    )
    result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Klinik bulunamadı")
    return ClinicResponse.model_validate(clinic)


async def update_clinic(
    clinic_id: uuid.UUID, data: ClinicUpdateRequest, db: AsyncSession
) -> ClinicResponse:
    await db.execute(
        text("SELECT set_config('app.current_clinic_id', :cid, true)").bindparams(cid=str(clinic_id)),
    )
    result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Klinik bulunamadı")

    if data.name is not None:
        clinic.name = data.name

    if data.settings is not None:
        # Mevcut ayarları koru, sadece gönderilen alanları güncelle
        current: dict = dict(clinic.settings or {})
        current.update(data.settings.model_dump(exclude_none=True))
        clinic.settings = current

    await db.flush()
    return ClinicResponse.model_validate(clinic)
