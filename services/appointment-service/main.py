"""
DentAI Flow — Appointment & Waitlist Service
Sorumluluk: Branş bazlı randevu yönetimi, akıllı yedek listesi motoru,
            iptal durumunda otonom hasta atama ve RabbitMQ event yayınlama.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.broker import close_broker, connect_broker
from app.core.config import settings
from app.routers import appointments_router, waitlist_router, patient_notes_router

# ── Security ──────────────────────────────────────────────
from shared.security_headers import SecurityHeadersMiddleware
from shared.csrf_protection import CSRFMiddleware
from shared.exception_handler import setup_global_exception_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_broker()
    logger.info("Appointment Service başlatıldı (port %s)", settings.SERVICE_PORT)
    yield
    # Shutdown
    await close_broker()
    from app.core.database import engine
    await engine.dispose()


app = FastAPI(
    title="DentAI Flow — Appointment Service",
    version="1.0.0",
    description=(
        "Branş bazlı akıllı randevu & yedek liste yönetimi. "
        "İptal → WaitlistEngine → RabbitMQ event zinciri."
    ),
    lifespan=lifespan,
)

# ── Middleware Stack (order matters!) ───────────────────
# 1. Security headers must come first
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF protection
csrf_secret = getattr(settings, "SECRET_KEY", getattr(settings, "JWT_SECRET", "csrf_fallback_secret"))
app.add_middleware(CSRFMiddleware, secret=csrf_secret)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token", "X-Request-ID"],  # Allow custom CSRF headers
)

# ── Global Exception Handler ───────────────────────────
setup_global_exception_handler(app, logger)

# ── Router'lar ────────────────────────────────────────────
app.include_router(appointments_router)
app.include_router(waitlist_router)
app.include_router(patient_notes_router)


@app.get("/health", tags=["Health"])
async def health_check():
    from fastapi.responses import JSONResponse
    from app.core.broker import is_broker_connected
    checks: dict = {}
    status = "ok"
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"
        status = "degraded"
    checks["rabbitmq"] = "ok" if is_broker_connected() else "disconnected"
    if checks["rabbitmq"] != "ok":
        status = "degraded"
    payload = {"status": status, "service": "appointment-service", "checks": checks}
    if status == "degraded":
        return JSONResponse(status_code=503, content=payload)
    return payload
