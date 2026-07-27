from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

METRICS_REGISTRY = CollectorRegistry(auto_describe=True)
WEBHOOK_REQUESTS_TOTAL = Counter(
    "dentai_webhook_requests_total",
    "Total webhook and ingestion HTTP requests handled by the WhatsApp ingestion service.",
    labelnames=("method", "path", "status"),
    registry=METRICS_REGISTRY,
)
WEBHOOK_REQUEST_DURATION_SECONDS = Histogram(
    "dentai_webhook_request_duration_seconds",
    "Webhook and ingestion HTTP request duration in seconds.",
    labelnames=("method", "path"),
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0),
    registry=METRICS_REGISTRY,
)
WEBHOOK_DISPATCH_TOTAL = Counter(
    "dentai_webhook_dispatch_total",
    "Total number of Celery dispatch attempts from the webhook handler.",
    labelnames=("outcome",),
    registry=METRICS_REGISTRY,
)


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    WEBHOOK_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()
    WEBHOOK_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)


def record_webhook_dispatch(outcome: str) -> None:
    WEBHOOK_DISPATCH_TOTAL.labels(outcome=outcome).inc()


def render_metrics() -> bytes:
    return generate_latest(METRICS_REGISTRY)


__all__ = [
    "CONTENT_TYPE_LATEST",
    "observe_http_request",
    "record_webhook_dispatch",
    "render_metrics",
]
