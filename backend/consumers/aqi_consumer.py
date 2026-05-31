"""
AQI evaluator consumer.

Consumes `sensor-raw` → validates with `SensorEvent` → computes EPA AQI via
`services.aqi_service.build_aqi_result` → upserts to MongoDB `aqi_results`
keyed by `(sensor_id, timestamp)`.

This consumer is INDEPENDENT of `raw_writer_consumer`:
  * separate consumer group (`aqi-evaluator-group`)
  * Kafka delivers every `sensor-raw` message to both groups in parallel
  * adding/removing this consumer never affects raw persistence

The consumer is thin by design — all AQI logic lives in `services/aqi_service.py`.

Run as a standalone process:
    python -m consumers.aqi_consumer
"""

import asyncio
import signal
from typing import List, Tuple

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from core.config import settings
from core.kafka_client import get_consumer
from core.logger import get_logger
from core.mongo_client import (
    aqi_results,
    close_mongo_connection,
    connect_to_mongo,
    ensure_aqi_indexes,
)
from services.aqi_service import AQIComputationError, build_aqi_result
from streaming.schemas import SensorEvent

logger = get_logger(__name__)

GETMANY_TIMEOUT_MS = 1000
GETMANY_MAX_RECORDS = 200


# ---------------------------------------------------------------------------
# Validation + AQI computation per record
# ---------------------------------------------------------------------------

def _build_ops(records) -> Tuple[List[UpdateOne], int, int]:
    """Process a batch of records.

    Returns:
        (upsert_ops, validation_skipped, compute_skipped)
    """
    ops: List[UpdateOne] = []
    validation_skipped = 0
    compute_skipped = 0

    for record in records:
        # 1. Validate the Kafka payload against the canonical schema.
        try:
            event = SensorEvent.model_validate(record.value)
        except ValidationError as e:
            validation_skipped += 1
            logger.warning(
                "Skipping invalid message key=%s partition=%s offset=%s errors=%s",
                record.key,
                record.partition,
                record.offset,
                e.errors(include_url=False),
            )
            continue
        except Exception as e:
            validation_skipped += 1
            logger.warning(
                "Skipping unparseable message key=%s offset=%s err=%s",
                record.key,
                record.offset,
                e,
            )
            continue

        # 2. Compute AQI (uses only pollutant fields; weather is ignored).
        try:
            result = build_aqi_result(event)
        except AQIComputationError as e:
            compute_skipped += 1
            logger.warning("AQI compute skipped: %s", e)
            continue
        except Exception as e:
            compute_skipped += 1
            logger.error(
                "Unexpected AQI error sensor=%s ts=%s err=%s",
                event.sensor_id,
                event.timestamp,
                e,
            )
            continue

        # 3. Stage the upsert. Key is (sensor_id, timestamp); `$set` overwrites
        #    the previous AQI evaluation for that exact moment if a redelivery
        #    arrives with the same timestamp.
        doc = result.to_doc()
        ops.append(
            UpdateOne(
                {"sensor_id": doc["sensor_id"], "timestamp": doc["timestamp"]},
                {"$set": doc},
                upsert=True,
            )
        )

    return ops, validation_skipped, compute_skipped


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

async def _persist(ops: List[UpdateOne]) -> dict:
    """Bulk-write upserts. Returns counters."""
    if not ops:
        return {"upserted": 0, "modified": 0, "errors": 0}

    coll = aqi_results()
    try:
        result = await coll.bulk_write(ops, ordered=False)
        return {
            "upserted": result.upserted_count,
            "modified": result.modified_count,
            "errors": 0,
        }
    except BulkWriteError as bwe:
        details = bwe.details or {}
        write_errors = details.get("writeErrors", []) or []
        for e in write_errors:
            logger.error(
                "Mongo write error code=%s msg=%s",
                e.get("code"),
                e.get("errmsg"),
            )
        return {
            "upserted": details.get("nUpserted", 0),
            "modified": details.get("nModified", 0),
            "errors": len(write_errors),
        }
    except Exception as e:
        logger.exception("Mongo bulk_write failed: %s", e)
        return {"upserted": 0, "modified": 0, "errors": len(ops)}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_consumer() -> None:
    logger.info(
        "AQI consumer starting | topic=%s | group=%s | bootstrap=%s",
        settings.KAFKA_TOPIC_SENSOR_RAW,
        settings.KAFKA_CONSUMER_GROUP_AQI,
        settings.KAFKA_BOOTSTRAP_SERVERS,
    )

    await connect_to_mongo()
    await ensure_aqi_indexes()

    consumer: AIOKafkaConsumer = await get_consumer(
        topics=settings.KAFKA_TOPIC_SENSOR_RAW,
        group_id=settings.KAFKA_CONSUMER_GROUP_AQI,
    )

    stop_event = asyncio.Event()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received — finishing current batch and stopping")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    totals = {
        "received": 0,
        "upserted": 0,
        "modified": 0,
        "validation_skipped": 0,
        "compute_skipped": 0,
        "write_errors": 0,
    }

    try:
        while not stop_event.is_set():
            batch = await consumer.getmany(
                timeout_ms=GETMANY_TIMEOUT_MS,
                max_records=GETMANY_MAX_RECORDS,
            )
            if not batch:
                continue

            records = [r for parts in batch.values() for r in parts]
            ops, val_skipped, comp_skipped = _build_ops(records)
            persist_result = await _persist(ops)

            totals["received"] += len(records)
            totals["upserted"] += persist_result["upserted"]
            totals["modified"] += persist_result["modified"]
            totals["validation_skipped"] += val_skipped
            totals["compute_skipped"] += comp_skipped
            totals["write_errors"] += persist_result["errors"]

            logger.info(
                "Batch | received=%d processed=%d upserted=%d modified=%d "
                "val_skipped=%d compute_skipped=%d write_errors=%d "
                "| totals: recv=%d up=%d mod=%d vs=%d cs=%d we=%d",
                len(records),
                len(ops),
                persist_result["upserted"],
                persist_result["modified"],
                val_skipped,
                comp_skipped,
                persist_result["errors"],
                totals["received"],
                totals["upserted"],
                totals["modified"],
                totals["validation_skipped"],
                totals["compute_skipped"],
                totals["write_errors"],
            )
    finally:
        await consumer.stop()
        await close_mongo_connection()
        logger.info(
            "AQI consumer stopped | totals: recv=%d up=%d mod=%d "
            "val_skip=%d compute_skip=%d errors=%d",
            totals["received"],
            totals["upserted"],
            totals["modified"],
            totals["validation_skipped"],
            totals["compute_skipped"],
            totals["write_errors"],
        )


if __name__ == "__main__":
    try:
        asyncio.run(run_consumer())
    except KeyboardInterrupt:
        pass
