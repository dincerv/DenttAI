from __future__ import annotations

import logging
from typing import Iterable

import redis
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

from app.core.config import settings

logger = logging.getLogger(__name__)

QUEUE_NAMES = ("appointments", "whatsapp", "ai", "default")
TASK_NAME_SET_KEY = "dentai:metrics:task_names"
TASK_KEY_PREFIX = "dentai:metrics:task"

METRICS_REGISTRY = CollectorRegistry(auto_describe=True)
WEBHOOK_REQUESTS_TOTAL = Counter(
    "dentai_webhook_requests_total",
    "Total webhook and integration HTTP requests handled by the integration service.",
    labelnames=("method", "path", "status"),
    registry=METRICS_REGISTRY,
)
WEBHOOK_REQUEST_DURATION_SECONDS = Histogram(
    "dentai_webhook_request_duration_seconds",
    "Webhook and integration HTTP request duration in seconds.",
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


class RedisMetricsCollector:
    def collect(self) -> Iterable[GaugeMetricFamily | CounterMetricFamily]:
        client = _get_redis_client()
        if client is None:
            return []

        try:
            task_names = sorted(client.smembers(TASK_NAME_SET_KEY))
        except redis.RedisError as exc:
            logger.warning("Failed to read metrics task names from Redis: %s", exc)
            return []

        queue_depth_metric = GaugeMetricFamily(
            "dentai_celery_queue_depth",
            "Current queue depth per Celery queue.",
            labels=["queue"],
        )
        task_processed_metric = CounterMetricFamily(
            "dentai_celery_task_processed_total",
            "Total processed Celery tasks by task name and outcome.",
            labels=["task", "status"],
        )
        task_duration_avg_metric = GaugeMetricFamily(
            "dentai_celery_task_duration_avg_seconds",
            "Average Celery task duration in seconds.",
            labels=["task"],
        )
        task_duration_last_metric = GaugeMetricFamily(
            "dentai_celery_task_duration_last_seconds",
            "Last observed Celery task duration in seconds.",
            labels=["task"],
        )

        for queue_name in QUEUE_NAMES:
            try:
                queue_depth_metric.add_metric([queue_name], float(client.llen(queue_name)))
            except redis.RedisError as exc:
                logger.warning("Failed to read Redis queue depth for %s: %s", queue_name, exc)
                queue_depth_metric.add_metric([queue_name], 0.0)

        for task_name in task_names:
            try:
                counts = client.hgetall(f"{TASK_KEY_PREFIX}:{task_name}:counts")
                durations = client.hgetall(f"{TASK_KEY_PREFIX}:{task_name}:durations")
            except redis.RedisError as exc:
                logger.warning("Failed to read Redis task metrics for %s: %s", task_name, exc)
                continue

            for status_name, raw_count in counts.items():
                task_processed_metric.add_metric([task_name, status_name], float(raw_count))

            duration_sum = float(durations.get("sum", 0.0))
            duration_count = float(durations.get("count", 0.0))
            duration_last = float(durations.get("last", 0.0))

            task_duration_last_metric.add_metric([task_name], duration_last)
            task_duration_avg_metric.add_metric(
                [task_name],
                duration_sum / duration_count if duration_count else 0.0,
            )

        return [
            queue_depth_metric,
            task_processed_metric,
            task_duration_avg_metric,
            task_duration_last_metric,
        ]

_redis_client: redis.Redis | None = None


def _get_redis_client() -> redis.Redis | None:
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    redis_url = (
        getattr(settings, "REDIS_URL", None)
        or getattr(settings, "CELERY_BACKEND_URL", None)
        or getattr(settings, "CELERY_BROKER_URL", None)
    )
    if not redis_url:
        return None

    try:
        _redis_client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1.0)
    except redis.RedisError as exc:
        logger.warning("Failed to create Redis metrics client: %s", exc)
        return None

    return _redis_client


METRICS_REGISTRY.register(RedisMetricsCollector())


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    WEBHOOK_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()
    WEBHOOK_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)


def record_webhook_dispatch(outcome: str) -> None:
    WEBHOOK_DISPATCH_TOTAL.labels(outcome=outcome).inc()


def record_celery_task_result(task_name: str, status: str, duration_seconds: float) -> None:
    client = _get_redis_client()
    if client is None:
        return

    task_key = f"{TASK_KEY_PREFIX}:{task_name}"

    try:
        pipeline = client.pipeline()
        pipeline.sadd(TASK_NAME_SET_KEY, task_name)
        pipeline.hincrby(f"{task_key}:counts", status, 1)
        pipeline.hincrbyfloat(f"{task_key}:durations", "sum", duration_seconds)
        pipeline.hincrby(f"{task_key}:durations", "count", 1)
        pipeline.hset(f"{task_key}:durations", "last", duration_seconds)
        pipeline.execute()
    except redis.RedisError as exc:
        logger.warning("Failed to persist Celery metrics for %s: %s", task_name, exc)


def render_metrics() -> bytes:
    return generate_latest(METRICS_REGISTRY)


__all__ = [
    "CONTENT_TYPE_LATEST",
    "observe_http_request",
    "record_celery_task_result",
    "record_webhook_dispatch",
    "render_metrics",
]
