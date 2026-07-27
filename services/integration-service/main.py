"""
DentAI Flow — Integration Service
Sorumluluk: Harici klinik yazılımlarından (DentSoft vb.) hasta ve randevu
            verilerini içe aktarma; duplicate korumalı mapping katmanı.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.routers import router
from app.core.config import settings
from app.core.metrics import CONTENT_TYPE_LATEST, render_metrics, observe_http_request

# ── Security ──────────────────────────────────────────────
from shared.security_headers import SecurityHeadersMiddleware
from shared.csrf_protection import CSRFMiddleware
from shared.exception_handler import setup_global_exception_handler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="DentAI Flow — Integration Service",
    version="1.0.0",
    description="Harici klinik yazılımlarından hasta ve randevu içe aktarma (DentSoft mapping)",
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


@app.middleware("http")
async def prometheus_metrics_middleware(request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    started_at = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        observe_http_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_seconds=time.perf_counter() - started_at,
        )

app.include_router(router)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)


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
    payload = {"status": status, "service": "integration-service", "checks": checks}
    if status == "degraded":
        return JSONResponse(status_code=503, content=payload)
    return payload
