"""
Lakehouse writer consumer.

Consumes `sensor-raw` → validates with `SensorEvent` → buffers events in
memory → flushes them to date-partitioned Parquet files under
`settings.LAKEHOUSE_PATH`.

Independent of `raw_writer_consumer` and `aqi_consumer`:
  * separate consumer group (`lakehouse-writer-group`)
  * Kafka delivers every sensor-raw message to all three groups in parallel
  * losing the lakehouse writer does not affect AQI or the API

Flush triggers (whichever first):
  - in-memory buffer reaches `LAKEHOUSE_BATCH_SIZE` events
  - `LAKEHOUSE_FLUSH_INTERVAL_SECONDS` elapsed since last flush

On shutdown, the buffer is flushed one last time so nothing is lost.
"""

import asyncio
import signal
from pathlib import Path

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from core.config import settings
from core.kafka_client import get_consumer
from core.logger import get_logger
from lakehouse.writer import LakehouseBatchWriter
from streaming.schemas import SensorEvent

logger = get_logger(__name__)

GETMANY_TIMEOUT_MS = 1000
GETMANY_MAX_RECORDS = 200


async def run_consumer() -> None:
    logger.info(
        "Lakehouse writer starting | topic=%s | group=%s | bootstrap=%s | "
        "path=%s | batch_size=%d | flush_interval=%ds",
        settings.KAFKA_TOPIC_SENSOR_RAW,
        settings.KAFKA_CONSUMER_GROUP_LAKEHOUSE,
        settings.KAFKA_BOOTSTRAP_SERVERS,
        settings.LAKEHOUSE_PATH,
        settings.LAKEHOUSE_BATCH_SIZE,
        settings.LAKEHOUSE_FLUSH_INTERVAL_SECONDS,
    )

    writer = LakehouseBatchWriter(
        root_path=Path(settings.LAKEHOUSE_PATH),
        max_batch_size=settings.LAKEHOUSE_BATCH_SIZE,
        max_age_seconds=settings.LAKEHOUSE_FLUSH_INTERVAL_SECONDS,
    )

    consumer: AIOKafkaConsumer = await get_consumer(
        topics=settings.KAFKA_TOPIC_SENSOR_RAW,
        group_id=settings.KAFKA_CONSUMER_GROUP_LAKEHOUSE,
    )

    stop_event = asyncio.Event()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received — flushing buffer and stopping")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows

    totals = {"received": 0, "buffered": 0, "written": 0, "skipped": 0}

    try:
        while not stop_event.is_set():
            batch = await consumer.getmany(
                timeout_ms=GETMANY_TIMEOUT_MS,
                max_records=GETMANY_MAX_RECORDS,
            )

            if batch:
                records = [r for parts in batch.values() for r in parts]
                for record in records:
                    totals["received"] += 1
                    try:
                        event = SensorEvent.model_validate(record.value)
                    except ValidationError as e:
                        totals["skipped"] += 1
                        logger.warning(
                            "Skipping invalid message key=%s offset=%s errors=%s",
                            record.key, record.offset,
                            e.errors(include_url=False),
                        )
                        continue
                    except Exception as e:
                        totals["skipped"] += 1
                        logger.warning(
                            "Skipping unparseable message key=%s offset=%s err=%s",
                            record.key, record.offset, e,
                        )
                        continue
                    writer.add(event)
                    totals["buffered"] += 1

            # Time-based or size-based flush.
            if writer.should_flush():
                written = writer.flush()
                totals["written"] += written
                logger.info(
                    "Lakehouse batch flushed | wrote=%d totals: recv=%d "
                    "buf=%d written=%d skip=%d",
                    written, totals["received"], totals["buffered"],
                    totals["written"], totals["skipped"],
                )
    finally:
        # Final flush so nothing in the buffer is lost.
        try:
            written = writer.flush()
            totals["written"] += written
            if written:
                logger.info("Final flush on shutdown | wrote=%d", written)
        except Exception as e:
            logger.exception("Final flush failed: %s", e)

        await consumer.stop()
        logger.info(
            "Lakehouse writer stopped | totals: recv=%d buf=%d written=%d skip=%d",
            totals["received"], totals["buffered"],
            totals["written"], totals["skipped"],
        )


if __name__ == "__main__":
    try:
        asyncio.run(run_consumer())
    except KeyboardInterrupt:
        pass
