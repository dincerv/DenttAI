"""
DentAI Flow - Analytics Service
Sorumluluk: Patron Dashboard, aylik iptal analizi,
yedek listeyle doldurulan randevularin finansal karsiligi
(Recovered Revenue) hesaplama ve raporlama.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import close_redis, init_redis
from app.core.config import settings
from app.routers import router
from shared.csrf_protection import CSRFMiddleware
from shared.exception_handler import setup_global_exception_handler
from shared.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


def _get_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if raw.strip():
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        if origins:
            return origins

    # Safe local defaults for dev environments.
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_redis()


app = FastAPI(
    title="DentAI Flow - Analytics Service",
    version="1.0.0",
    description="Patron Dashboard ve Recovered Revenue raporlama motoru",
    lifespan=lifespan,
)

# 1. Security headers
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF protection
csrf_secret = getattr(settings, "SECRET_KEY", getattr(settings, "JWT_SECRET", "csrf_fallback_secret"))
app.add_middleware(CSRFMiddleware, secret=csrf_secret)

# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token", "X-Request-ID"],
)

# Global exception handler
setup_global_exception_handler(app, logger)

app.include_router(router)


@app.get("/health")
async def health_check():
    from fastapi.responses import JSONResponse

    checks: dict = {}
    status = "ok"

    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"
        status = "degraded"

    try:
        from app.core.cache import _redis
        if _redis:
            await _redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not_initialized"
            status = "degraded"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        status = "degraded"

    payload = {"status": status, "service": "analytics-service", "checks": checks}
    if status == "degraded":
        return JSONResponse(status_code=503, content=payload)
    return payload
