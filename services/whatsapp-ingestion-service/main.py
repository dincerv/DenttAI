import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.core.config import settings
from app.core.metrics import CONTENT_TYPE_LATEST, observe_http_request, render_metrics
from app.routers.webhook import router as webhook_router
from shared.csrf_protection import CSRFMiddleware
from shared.exception_handler import setup_global_exception_handler
from shared.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(
    title="DentAI Flow - WhatsApp Ingestion Service",
    version="1.0.0",
    description="Dedicated webhook ingress service for WhatsApp events.",
)

app.add_middleware(SecurityHeadersMiddleware)
csrf_secret = settings.JWT_SECRET
app.add_middleware(CSRFMiddleware, secret=csrf_secret)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token", "X-Request-ID"],
)
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


app.include_router(webhook_router)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "whatsapp-ingestion-service"}
