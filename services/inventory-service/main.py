"""
DentAI Flow — Inventory Service
Sorumluluk: QR kodlu sarf malzeme takibi, döngüsel malzeme (Cycle Materials)
            ömür yönetimi ve anomali tespiti
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.routers import items_router, qr_router, cycle_router

# ── Security ──────────────────────────────────────────────
from shared.security_headers import SecurityHeadersMiddleware
from shared.csrf_protection import CSRFMiddleware
from shared.exception_handler import setup_global_exception_handler
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production'da migration kullanılır; create_all sadece development fallback
    import os
    if os.environ.get("ENVIRONMENT", "development") == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="DentAI Flow — Inventory Service",
    version="1.0.0",
    description="QR kodlu sarf malzeme ve döngüsel malzeme ömür takibi",
    lifespan=lifespan,
)

# ── Middleware Stack (order matters!) ───────────────────
# 1. Security headers must come first
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF protection
csrf_secret = settings.JWT_SECRET
app.add_middleware(CSRFMiddleware, secret=csrf_secret)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-CSRF-Token"],
)

# ── Global Exception Handler ───────────────────────────
setup_global_exception_handler(app, logger)

app.include_router(items_router)
app.include_router(qr_router)
app.include_router(cycle_router)


@app.get("/health")
async def health_check():
    from fastapi.responses import JSONResponse
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
    payload = {"status": status, "service": "inventory-service", "checks": checks}
    if status == "degraded":
        return JSONResponse(status_code=503, content=payload)
    return payload
# app.include_router(items.router, prefix="/items")
# app.include_router(cycle_materials.router, prefix="/cycle-materials")
# app.include_router(qr.router, prefix="/qr")
