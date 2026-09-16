"""
Tenant router: /tenants/me — Klinik okuma ve güncelleme
Yalnızca 'owner' rolüne sahip kullanıcılar erişebilir.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.schemas.tenant import ClinicResponse, ClinicUpdateRequest
from app.services.tenant_service import get_clinic, update_clinic

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get(
    "/me",
    response_model=ClinicResponse,
    summary="Klinik bilgilerini getir",
)
async def get_my_clinic(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClinicResponse:
    return await get_clinic(current_user["clinic_id"], db)


@router.patch(
    "/me",
    response_model=ClinicResponse,
    summary="Klinik adını veya ayarlarını güncelle (yalnızca owner)",
    dependencies=[Depends(require_role("owner"))],
)
async def update_my_clinic(
    data: ClinicUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClinicResponse:
    return await update_clinic(current_user["clinic_id"], data, db)
