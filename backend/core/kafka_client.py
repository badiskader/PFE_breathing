"""
Kafka producer/consumer factories built on aiokafka.

Streaming code stays thin: producer.py calls `get_producer()`, consumers
call `get_consumer(topic, group_id)`. Serialization is JSON UTF-8.
"""

import json
from typing import Iterable, Optional, Union

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def _json_serializer(value) -> bytes:
    return json.dumps(value, default=str).encode("utf-8")


def _json_deserializer(value: bytes):
    if value is None:
        return None
    return json.loads(value.decode("utf-8"))


def _key_serializer(key: Optional[str]) -> Optional[bytes]:
    if key is None:
        return None
    return str(key).encode("utf-8")


async def get_producer() -> AIOKafkaProducer:
    """
    Create and start a Kafka producer. Caller is responsible for `await producer.stop()`.
    """
    logger.info(
        "Starting Kafka producer (bootstrap=%s)", settings.KAFKA_BOOTSTRAP_SERVERS
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=_json_serializer,
        key_serializer=_key_serializer,
        enable_idempotence=True,
        acks="all",
    )
    await producer.start()
    return producer


async def get_consumer(
    topics: Union[str, Iterable[str]],
    group_id: str,
    auto_offset_reset: str = "earliest",
) -> AIOKafkaConsumer:
    """
    Create and start a Kafka consumer for one or more topics.
    Caller is responsible for `await consumer.stop()`.
    """
    topic_list = [topics] if isinstance(topics, str) else list(topics)
    logger.info(
        "Starting Kafka consumer (topics=%s, group=%s, bootstrap=%s)",
        topic_list,
        group_id,
        settings.KAFKA_BOOTSTRAP_SERVERS,
    )
    consumer = AIOKafkaConsumer(
        *topic_list,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        value_deserializer=_json_deserializer,
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
        enable_auto_commit=True,
        auto_offset_reset=auto_offset_reset,
    )
    await consumer.start()
    return consumer
