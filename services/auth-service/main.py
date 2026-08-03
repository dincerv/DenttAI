"""
DentAI Flow — Auth & Tenant Service
Sorumluluk: Multi-tenant JWT yetkilendirme, klinik izolasyonu (RLS)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth_router, tenants_router, admin_router, users_router

# ── Security ──────────────────────────────────────────────
from shared.security_headers import SecurityHeadersMiddleware
from shared.csrf_protection import CSRFMiddleware
from shared.exception_handler import setup_global_exception_handler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: bağlantı havuzu hazır (create_async_engine lazy bağlanır)
    yield
    # Shutdown: engine'i kapat
    from app.core.database import engine
    await engine.dispose()


app = FastAPI(
    title="DentAI Flow — Auth Service",
    version="1.0.0",
    description="Multi-tenant JWT yetkilendirme ve klinik izolasyonu (RLS)",
    root_path="/api/auth",
    lifespan=lifespan,
)

# ── Middleware Stack (order matters!) ───────────────────
# 1. Security headers must come first
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF protection
csrf_secret = settings.JWT_SECRET
app.add_middleware(CSRFMiddleware, secret=csrf_secret)

# 3. CORS — Vercel + localhost (CORS_ALLOWED_ORIGINS env)
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

# ── Router'lar ────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(admin_router)
app.include_router(users_router)


@app.get("/health", tags=["Health"])
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
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        status = "degraded"
    payload = {"status": status, "service": "auth-service", "checks": checks}
    if status == "degraded":
        return JSONResponse(status_code=503, content=payload)
    return payload
