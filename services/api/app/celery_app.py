"""
Celery Uyumluluk Shim — Monolith
================================
Gerçek Celery worker yok. `.delay()` / `.apply_async()` arka planda
ThreadPoolExecutor ile çalıştırılır (post-op, WhatsApp task'ları).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="celery-shim")


class _FakeTaskContext:
    """bind=True task'lar için self nesnesi."""

    def __init__(self) -> None:
        self.request = type("Request", (), {"retries": 0, "id": "local"})()

    def retry(self, exc: BaseException | None = None, **_kwargs: Any) -> None:
        if exc is not None:
            raise exc
        raise RuntimeError("Celery retry requested (shim)")


def _attach_async_api(func: Callable, *, bind: bool) -> Callable:
    def _run(*args: Any, **kwargs: Any) -> Any:
        try:
            if bind:
                return func(_FakeTaskContext(), *args, **kwargs)
            return func(*args, **kwargs)
        except Exception:
            logger.exception("Background task failed: %s", getattr(func, "__name__", func))
            raise

    def delay(*args: Any, **kwargs: Any):
        return _executor.submit(_run, *args, **kwargs)

    def apply_async(args: tuple | None = None, kwargs: dict | None = None, **_opts: Any):
        return _executor.submit(_run, *(args or ()), **(kwargs or {}))

    func.delay = delay  # type: ignore[attr-defined]
    func.apply_async = apply_async  # type: ignore[attr-defined]
    return func


def shared_task(func: Callable | None = None, **kwargs: Any):
    """Celery shared_task stub — .delay gerçekten çalıştırır."""
    bind = bool(kwargs.get("bind", False))

    if func is None:

        def decorator(f: Callable) -> Callable:
            return _attach_async_api(f, bind=bind)

        return decorator

    return _attach_async_api(func, bind=bind)


class _FakeCelery:
    def task(self, func: Callable | None = None, **kwargs: Any):
        return shared_task(func, **kwargs)

    def send_task(self, name: str, args: tuple | None = None, kwargs: dict | None = None, **_opts: Any):
        logger.warning("send_task stub ignored: %s", name)


app = _FakeCelery()
celery_app = app
Celery = _FakeCelery
