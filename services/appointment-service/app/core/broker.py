"""
RabbitMQ bağlantı ve event yayınlama katmanı.
aio-pika kullanır; async bağlantı havuzu ile production-grade.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import aio_pika
import aio_pika.abc
from aio_pika import DeliveryMode, ExchangeType, Message

from app.core.config import settings

logger = logging.getLogger(__name__)

# Uygulama genelinde paylaşılan bağlantı
_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect_broker() -> None:
    """Uygulama başlangıcında çağrılır. Cloud'da RabbitMQ yoksa opsiyonel geçilir."""
    global _connection, _channel, _exchange

    try:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        _channel = await _connection.channel()
        await _channel.set_qos(prefetch_count=10)

        _exchange = await _channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("RabbitMQ bağlantısı kuruldu: %s", settings.RABBITMQ_EXCHANGE)
    except Exception as e:
        _connection = None
        _channel = None
        _exchange = None
        if settings.RABBITMQ_OPTIONAL:
            logger.warning("RabbitMQ bağlanamadı (opsiyonel): %s", e)
            return
        raise


async def close_broker() -> None:
    """Uygulama kapatılırken çağrılır."""
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ bağlantısı kapatıldı.")


def is_broker_connected() -> bool:
    """RabbitMQ bağlantısının aktif olup olmadığını döner."""
    return _connection is not None and not _connection.is_closed


async def publish_event(routing_key: str, payload: dict[str, Any]) -> None:
    """
    Topic exchange'e event yayınlar.

    routing_key örnekleri:
        "appointment.cancelled"
        "waitlist.match_found"
        "appointment.confirmed"
    """
    if _exchange is None:
        logger.warning("Exchange hazır değil; event atlandı: %s", routing_key)
        return

    body = json.dumps(payload, default=str).encode()

    message = Message(
        body=body,
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
    )

    await _exchange.publish(message, routing_key=routing_key)
    logger.info("Event yayınlandı: %s | payload_size=%d bytes", routing_key, len(body))
