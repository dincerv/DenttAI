"""
Redis önbellek yardımcıları.

Kullanım:
    from app.core.cache import get_cache, set_cache, build_key

    async def my_report(clinic_id, ...):
        key = build_key("report_name", clinic_id, extra_param)
        cached = await get_cache(key)
        if cached:
            return cached
        data = await compute_expensive_report(...)
        await set_cache(key, data)
        return data
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

# Modül seviyesinde bağlantı — lifespan'de başlatılır
_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def build_key(*parts: Any) -> str:
    """Önbellek anahtarı oluşturur: 'analytics:<part1>:<part2>:...'"""
    return "analytics:" + ":".join(str(p) for p in parts)


async def get_cache(key: str) -> Any | None:
    if _redis is None:
        return None
    raw = await _redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cache(key: str, value: Any, ttl: int = settings.CACHE_TTL_SECONDS) -> None:
    if _redis is None:
        return
    await _redis.set(key, json.dumps(value, default=str), ex=ttl)


async def invalidate_clinic(clinic_id: str) -> None:
    """Bir kliniğe ait tüm önbellek girdilerini siler."""
    if _redis is None:
        return
    pattern = f"analytics:*:{clinic_id}:*"
    keys = await _redis.keys(pattern)
    if keys:
        await _redis.delete(*keys)
