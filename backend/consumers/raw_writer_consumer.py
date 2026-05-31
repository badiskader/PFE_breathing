"""
Raw data writer consumer.

Consumes `sensor-raw` → validates with `SensorEvent` → inserts the FULL
canonical observation into MongoDB `sensor_readings`.

This consumer:
  * performs NO computation (no AQI, no normalization, no enrichment)
  * preserves ALL 14 raw fields verbatim
  * uses its own consumer group so it runs in parallel with AQI / lakehouse
    consumers on the same topic
  * is idempotent via a unique index on (sensor_id, timestamp): a redelivered
    Kafka message produces a DuplicateKeyError that is logged and ignored

Run as a standalone process:
    python -m consumers.raw_writer_consumer
"""

import asyncio
import signal
from typing import List

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError
from pymongo.errors import BulkWriteError

from core.config import settings
from core.kafka_client import get_consumer
from core.logger import get_logger
from core.mongo_client import (
    close_mongo_connection,
    connect_to_mongo,
    ensure_sensor_readings_indexes,
    sensor_readings,
)
from streaming.schemas import SensorEvent

logger = get_logger(__name__)

# Batch tuning — keep modest so failures don't burn through too many messages.
GETMANY_TIMEOUT_MS = 1000
GETMANY_MAX_RECORDS = 200

# Mongo duplicate-key error code (E11000).
MONGO_DUPLICATE_KEY = 11000


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_records(records) -> List[dict]:
    """Validate a list of aiokafka ConsumerRecords → list of insert-ready dicts.

    `mode="python"` keeps datetime as a native datetime so Mongo stores it
    as a BSON date (not an ISO string).
    """
    docs: List[dict] = []
    for record in records:
        try:
            event = SensorEvent.model_validate(record.value)
        except ValidationError as e:
            logger.warning(
                "Skipping invalid message key=%s partition=%s offset=%s errors=%s",
                record.key,
                record.partition,
                record.offset,
                e.errors(include_url=False),
            )
            continue
        except Exception as e:
            logger.warning(
                "Skipping unparseable message key=%s partition=%s offset=%s err=%s",
                record.key,
                record.partition,
                record.offset,
                e,
            )
            continue

        docs.append(event.model_dump(mode="python"))
    return docs


# ---------------------------------------------------------------------------
# Insertion
# ---------------------------------------------------------------------------

async def _insert_batch(docs: List[dict]) -> tuple[int, int, int]:
    """Insert a batch into sensor_readings.

    Returns (inserted, duplicates_skipped, other_errors).
    """
    if not docs:
        return 0, 0, 0

    coll = sensor_readings()
    try:
        result = await coll.insert_many(docs, ordered=False)
        return len(result.inserted_ids), 0, 0

    except BulkWriteError as bwe:
        details = bwe.details or {}
        inserted = details.get("nInserted", 0)
        write_errors = details.get("writeErrors", []) or []

        duplicates = sum(1 for e in write_errors if e.get("code") == MONGO_DUPLICATE_KEY)
        other = 0
        for e in write_errors:
            if e.get("code") != MONGO_DUPLICATE_KEY:
                other += 1
                logger.error(
                    "Mongo write error code=%s msg=%s",
                    e.get("code"),
                    e.get("errmsg"),
                )
        return inserted, duplicates, other

    except Exception as e:
        # Hard failure of the whole batch (connection lost, etc.).
        # Log and report all docs as failed so caller can react.
        logger.exception("Mongo bulk insert failed: %s", e)
        return 0, 0, len(docs)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_consumer() -> None:
    logger.info(
        "Raw writer starting | topic=%s | group=%s | bootstrap=%s",
        settings.KAFKA_TOPIC_SENSOR_RAW,
        settings.KAFKA_CONSUMER_GROUP_RAW,
        settings.KAFKA_BOOTSTRAP_SERVERS,
    )

    # Mongo first — fail fast if DB unreachable; also ensures index exists
    # before the first insert.
    await connect_to_mongo()
    await ensure_sensor_readings_indexes()

    consumer: AIOKafkaConsumer = await get_consumer(
        topics=settings.KAFKA_TOPIC_SENSOR_RAW,
        group_id=settings.KAFKA_CONSUMER_GROUP_RAW,
    )

    # Graceful shutdown.
    stop_event = asyncio.Event()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received — finishing current batch and stopping")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Windows: not supported via loop; KeyboardInterrupt still works.
            pass

    totals = {"received": 0, "inserted": 0, "duplicates": 0, "validation_skipped": 0, "write_errors": 0}

    try:
        while not stop_event.is_set():
            batch = await consumer.getmany(
                timeout_ms=GETMANY_TIMEOUT_MS,
                max_records=GETMANY_MAX_RECORDS,
            )
            if not batch:
                continue

            records = [r for partition_recs in batch.values() for r in partition_recs]
            docs = _validate_records(records)
            inserted, duplicates, write_errors = await _insert_batch(docs)
            validation_skipped = len(records) - len(docs)

            totals["received"] += len(records)
            totals["inserted"] += inserted
            totals["duplicates"] += duplicates
            totals["validation_skipped"] += validation_skipped
            totals["write_errors"] += write_errors

            logger.info(
                "Batch | received=%d validated=%d inserted=%d duplicates=%d "
                "validation_skipped=%d write_errors=%d "
                "| totals: received=%d inserted=%d duplicates=%d skipped=%d errors=%d",
                len(records),
                len(docs),
                inserted,
                duplicates,
                validation_skipped,
                write_errors,
                totals["received"],
                totals["inserted"],
                totals["duplicates"],
                totals["validation_skipped"],
                totals["write_errors"],
            )
    finally:
        await consumer.stop()
        await close_mongo_connection()
        logger.info(
            "Raw writer stopped | totals: received=%d inserted=%d duplicates=%d "
            "skipped=%d errors=%d",
            totals["received"],
            totals["inserted"],
            totals["duplicates"],
            totals["validation_skipped"],
            totals["write_errors"],
        )


if __name__ == "__main__":
    try:
        asyncio.run(run_consumer())
    except KeyboardInterrupt:
        pass
