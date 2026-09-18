"""Invoice router — /invoices"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.invoice import (
    EligiblePaymentsResponse,
    InvoiceCreate,
    InvoiceFromPayment,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceSummaryResponse,
)
from app.services.invoice_service import (
    cancel_invoice,
    create_from_payment,
    create_invoice,
    get_invoice,
    get_summary,
    issue_invoice,
    list_eligible_payments,
    list_invoices,
)
from shared.auth_middleware import (
    require_page_permission,
    require_role,
    set_rls_context,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("/summary", response_model=InvoiceSummaryResponse)
async def invoice_summary(
    claims: dict = Depends(require_page_permission("invoices")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await get_summary(db, claims["clinic_id"])


@router.get("/eligible-payments", response_model=EligiblePaymentsResponse)
async def eligible_payments(
    claims: dict = Depends(require_page_permission("invoices")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await list_eligible_payments(db, claims["clinic_id"])


@router.get("", response_model=InvoiceListResponse)
async def list_invoices_endpoint(
    status_filter: str | None = Query(None, alias="status"),
    invoice_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    claims: dict = Depends(require_page_permission("invoices")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await list_invoices(
        db, claims["clinic_id"],
        status_filter=status_filter,
        invoice_type=invoice_type,
        limit=limit,
        offset=offset,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice_endpoint(
    invoice_id: UUID,
    claims: dict = Depends(require_page_permission("invoices")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await get_invoice(db, invoice_id)


@router.post("", response_model=InvoiceResponse, status_code=201)
async def create_invoice_endpoint(
    body: InvoiceCreate,
    claims: dict = Depends(require_role("owner", "assistant", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await create_invoice(db, claims["clinic_id"], body, claims["user_id"])


@router.post("/from-payment/{payment_id}", response_model=InvoiceResponse, status_code=201)
async def create_from_payment_endpoint(
    payment_id: UUID,
    body: InvoiceFromPayment,
    claims: dict = Depends(require_role("owner", "assistant", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await create_from_payment(db, claims["clinic_id"], payment_id, body, claims["user_id"])


@router.post("/{invoice_id}/issue", response_model=InvoiceResponse)
async def issue_invoice_endpoint(
    invoice_id: UUID,
    claims: dict = Depends(require_role("owner", "assistant", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await issue_invoice(db, claims["clinic_id"], invoice_id)


@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
async def cancel_invoice_endpoint(
    invoice_id: UUID,
    claims: dict = Depends(require_role("owner", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, claims["clinic_id"])
    return await cancel_invoice(db, invoice_id)
