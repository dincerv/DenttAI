"""
Metrik shim — Prometheus/Celery metrikleri monolitte opsiyonel.
Eski task'lar import kırılmasın diye no-op.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def record_celery_task_result(
    task_name: str,
    status: str,
    duration_seconds: float | None = None,
    **_kwargs: Any,
) -> None:
    logger.debug(
        "task_metric name=%s status=%s duration=%s",
        task_name,
        status,
        duration_seconds,
    )
