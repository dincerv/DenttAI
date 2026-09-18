"""
DentAI Flow — Monolith API
Tüm mikroservislerin birleşimi: auth, randevu, stok, analitik, entegrasyon, WhatsApp
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler

# ── Middleware'ler ────────────────────────────────────────
from shared.csrf_protection import CSRFMiddleware
from shared.rate_limiter import RateLimitMiddleware
from shared.security_headers import SecurityHeadersMiddleware

# ── Router'lar ────────────────────────────────────────────
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.tenants import router as tenants_router
from app.routers.admin import router as admin_router
from app.routers.appointments import router as appointments_router
from app.routers.waitlist import router as waitlist_router
from app.routers.patient_notes import router as patient_notes_router
from app.routers.inventory_items import router as inventory_items_router
from app.routers.inventory_qr import router as inventory_qr_router
from app.routers.inventory_cycle import router as inventory_cycle_router
from app.routers.analytics import router as analytics_router
from app.routers.whatsapp import router as whatsapp_router
from app.routers.webhook import router as webhook_router
from app.routers.pms import router as pms_router
from app.routers.whatsapp_ingest import router as whatsapp_ingest_router
from app.routers.payments import router as payments_router
from app.routers.invoices import router as invoices_router
from app.routers.prescriptions import router as prescriptions_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DentAI Flow API",
    version="2.0.0",
    description="Diş kliniklerinde randevu, stok, WhatsApp ve analitik yönetimi",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-CSRF-Token"],
)

# ── Güvenlik middleware'leri ──────────────────────────────
# Sıra (Starlette: son eklenen en dışta): CORS → RateLimit → CSRF → SecurityHeaders → app
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware, secret=settings.JWT_SECRET)
app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)

# ── Router'lar (/api prefix — gateway uyumluluğu) ─────────
# Frontend apiClient zaten /api prefix ekliyor; bu prefix'ler
# eski gateway route'larıyla %100 uyumlu.

app.include_router(auth_router,            prefix="/api")        # /api/auth/*
app.include_router(users_router,           prefix="/api")        # /api/users/*
app.include_router(tenants_router,         prefix="/api")        # /api/tenants/*
app.include_router(admin_router,           prefix="/api")        # /api/admin/*
app.include_router(appointments_router,    prefix="/api")        # /api/appointments/*
app.include_router(waitlist_router,        prefix="/api")        # /api/waitlist/*
app.include_router(patient_notes_router,   prefix="/api")        # /api/patient-notes/*
app.include_router(inventory_items_router, prefix="/api")        # /api/inventory/*
app.include_router(inventory_qr_router,    prefix="/api")        # /api/inventory/qr/*
app.include_router(inventory_cycle_router, prefix="/api")        # /api/inventory/cycle/*
app.include_router(analytics_router,       prefix="/api")        # /api/analytics/*
app.include_router(whatsapp_router,        prefix="/api")        # /api/integration/*
app.include_router(webhook_router,         prefix="/api")        # /api/integration/webhook/*
app.include_router(pms_router,             prefix="/api")        # /api/integration/pms/*
app.include_router(whatsapp_ingest_router, prefix="/api")        # /api/whatsapp/*
app.include_router(payments_router,        prefix="/api")        # /api/payments/*
app.include_router(invoices_router,        prefix="/api")        # /api/invoices/*
app.include_router(prescriptions_router,   prefix="/api")        # /api/prescriptions/*


# ── Lifecycle ─────────────────────────────────────────────
@app.on_event("startup")
async def startup() -> None:
    logger.info("DentAI Flow API başlatılıyor...")
    await start_scheduler()
    logger.info(f"API hazır — port: {settings.SERVICE_PORT}, ortam: {settings.ENVIRONMENT}")


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("DentAI Flow API kapatılıyor...")
    await stop_scheduler()


# ── Health Check ─────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "service": "dentai-api",
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/api/health", tags=["system"])
async def api_health():
    """Eski gateway health check uyumluluğu."""
    return {"status": "ok"}
