"""
Payment Router — /payments
Hasta bazlı borç/alacak takibi.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentSummaryResponse,
    PaymentUpdate,
    TransactionCreate,
)
from app.services.payment_service import (
    add_transaction,
    cancel_payment,
    create_payment,
    get_payment,
    get_summary,
    list_payments,
    update_payment,
)
from shared.auth_middleware import (
    get_verified_claims,
    require_page_permission,
    require_role,
    set_rls_context,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Özet ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=PaymentSummaryResponse)
async def payment_summary(
    claims: dict = Depends(get_verified_claims),
    db: AsyncSession = Depends(get_db),
):
    """Klinik geneli ödeme özeti — dashboard widget için."""
    clinic_id = claims["clinic_id"]  # Middleware zaten UUID'ye çevirdi
    await set_rls_context(db, clinic_id)
    return await get_summary(db, clinic_id)


# ── Listeleme ─────────────────────────────────────────────────────────────

@router.get("", response_model=PaymentListResponse)
async def list_payments_endpoint(
    status_filter: str | None = Query(None, alias="status"),
    patient_id: UUID | None = Query(None),
    overdue_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    claims: dict = Depends(require_page_permission("payments")),
    db: AsyncSession = Depends(get_db),
):
    """Klinik ödemelerini listele — filtreli."""
    clinic_id = claims["clinic_id"]
    await set_rls_context(db, clinic_id)
    return await list_payments(
        db, clinic_id,
        status_filter=status_filter,
        patient_id=patient_id,
        overdue_only=overdue_only,
        limit=limit,
        offset=offset,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_endpoint(
    payment_id: UUID,
    claims: dict = Depends(require_page_permission("payments")),
    db: AsyncSession = Depends(get_db),
):
    """Tek ödeme detayı + işlem geçmişi."""
    await set_rls_context(db, claims["clinic_id"])
    return await get_payment(db, payment_id)


# ── Oluşturma / güncelleme ────────────────────────────────────────────────

@router.post("", response_model=PaymentResponse, status_code=201)
async def create_payment_endpoint(
    body: PaymentCreate,
    claims: dict = Depends(require_role("owner", "assistant", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Yeni ödeme kaydı oluştur."""
    clinic_id = claims["clinic_id"]
    created_by = claims["user_id"]
    await set_rls_context(db, clinic_id)
    return await create_payment(db, clinic_id, body, created_by)


@router.patch("/{payment_id}", response_model=PaymentResponse)
async def update_payment_endpoint(
    payment_id: UUID,
    body: PaymentUpdate,
    claims: dict = Depends(require_role("owner", "assistant", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Ödeme bilgilerini güncelle (açıklama, vade tarihi, notlar)."""
    await set_rls_context(db, claims["clinic_id"])
    return await update_payment(db, payment_id, body)


@router.post("/{payment_id}/cancel", response_model=PaymentResponse)
async def cancel_payment_endpoint(
    payment_id: UUID,
    claims: dict = Depends(require_role("owner", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Ödemeyi iptal et (sadece owner/super_admin)."""
    await set_rls_context(db, claims["clinic_id"])
    return await cancel_payment(db, payment_id)


# ── İşlem (tahsilat) ─────────────────────────────────────────────────────

@router.post("/{payment_id}/transactions", response_model=PaymentResponse, status_code=201)
async def add_transaction_endpoint(
    payment_id: UUID,
    body: TransactionCreate,
    claims: dict = Depends(require_role("owner", "assistant", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Ödemeye tahsilat işlemi ekle — paid_amount otomatik güncellenir."""
    clinic_id = claims["clinic_id"]
    created_by = claims["user_id"]
    await set_rls_context(db, clinic_id)
    return await add_transaction(db, payment_id, clinic_id, body, created_by)
