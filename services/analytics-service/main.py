"""
DentAI Flow - Analytics Service
Sorumluluk: Patron Dashboard, aylik iptal analizi,
yedek listeyle doldurulan randevularin finansal karsiligi
(Recovered Revenue) hesaplama ve raporlama.
"""
import logging
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

    # Cloud healthcheck: postgres ayaktaysa 200 (redis degraded olsa bile)
    payload = {"status": status, "service": "analytics-service", "checks": checks}
    if checks.get("postgres") != "ok":
        return JSONResponse(status_code=503, content=payload)
    return payload

