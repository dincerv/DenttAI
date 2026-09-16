"""Router: QR üretme ve aktivasyon."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.qr import QRActivateRequest, QRActivateResponse, QRGenerateRequest, QRGenerateResponse
from app.services import activate_qr, generate_qr
from shared.auth_middleware import get_verified_claims, require_role, set_rls_context

router = APIRouter(prefix="/inventory/qr", tags=["inventory-qr"])


@router.post("/generate", response_model=QRGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_qr_code(
    body: QRGenerateRequest,
    claims: dict = Depends(require_role("owner", "doctor", "assistant")),
    db: AsyncSession = Depends(get_db),
):
    """Yeni bir döngüsel malzeme kaydı oluşturur ve QR kodu PNG (base64) döner."""
    await set_rls_context(db, claims["clinic_id"])
    return await generate_qr(req=body, clinic_id=claims["clinic_id"], db=db)


@router.post("/activate", response_model=QRActivateResponse)
async def activate_qr_code(
    body: QRActivateRequest,
    claims: dict = Depends(require_role("owner", "doctor", "assistant")),
    db: AsyncSession = Depends(get_db),
):
    """QR okutulduğunda malzemeyi kullanıma açar; start_date = bugün olarak ayarlanır."""
    await set_rls_context(db, claims["clinic_id"])
    return await activate_qr(qr_id=body.qr_id, clinic_id=claims["clinic_id"], db=db)
