"""
CSV replay → Kafka producer (IoT stream simulator).

CSV source schema (raw dataset columns)
---------------------------------------
sensor_id, center_latitude, center_longitude, sensor_radius_km, time,
pm10, pm2_5, nitrogen_dioxide, ozone, carbon_monoxide, sulphur_dioxide,
temperature_2m, relative_humidity_2m, wind_speed_10m, wind_direction_10m

The producer translates these CSV column names to the canonical schema
(`SensorEvent`) before publishing. Translation is the only place where
external naming conventions touch the system.

Behavior
--------
- Loads every *.csv in `CSV_DATA_PATH` and concatenates them.
- Groups rows by `sensor_id` (read from the CSV column, NOT the filename),
  sorts each sensor's rows by timestamp.
- If `ACTIVE_SENSOR_IDS` is set, filters at the row level.
- Each tick (every `SIMULATION_TICK_SECONDS`), publishes one message per
  active sensor to `KAFKA_TOPIC_SENSOR_RAW`.
- Partition key = sensor_id → preserves per-sensor ordering.
- Validates every row via `SensorEvent`; bad rows logged + skipped.
- On EOF, loops back to row 0 if `PRODUCER_LOOP_ON_EOF` is true.
"""

import asyncio
import signal
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from aiokafka import AIOKafkaProducer
from pydantic import ValidationError

from core.config import settings
from core.kafka_client import get_producer
from core.logger import get_logger
from streaming.schemas import SensorEvent

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# CSV column → canonical schema name mapping
# (The ONLY place where dataset-specific naming touches the codebase.)
# ---------------------------------------------------------------------------

CSV_COLUMN_MAP: Dict[str, str] = {
    # identity & time
    "sensor_id": "sensor_id",
    "time": "timestamp",
    # location
    "center_latitude": "latitude",
    "center_longitude": "longitude",
    "sensor_radius_km": "sensor_radius_km",
    # pollutants
    "pm2_5": "PM25",
    "pm10": "PM10",
    "nitrogen_dioxide": "NO2",
    "sulphur_dioxide": "SO2",
    "carbon_monoxide": "CO",
    "ozone": "O3",
    # weather
    "temperature_2m": "temperature_2m",
    "relative_humidity_2m": "relative_humidity_2m",
    "wind_speed_10m": "wind_speed_10m",
    "wind_direction_10m": "wind_direction_10m",
}

REQUIRED_CSV_COLUMNS = set(CSV_COLUMN_MAP.keys())
CANONICAL_COLUMNS = list(CSV_COLUMN_MAP.values())


# ---------------------------------------------------------------------------
# CSV loading & grouping
# ---------------------------------------------------------------------------

def _load_all_csvs(csv_dir: Path) -> pd.DataFrame:
    """Read every CSV in csv_dir, validate columns, rename to canonical, concat."""
    if not csv_dir.exists():
        raise FileNotFoundError(f"CSV directory does not exist: {csv_dir}")

    paths = sorted(csv_dir.glob("*.csv"))
    if not paths:
        raise RuntimeError(f"No CSV files found in {csv_dir}")

    frames = []
    for path in paths:
        df = pd.read_csv(path)
        missing = REQUIRED_CSV_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"{path.name} is missing required columns: {sorted(missing)}"
            )
        # Rename CSV columns → canonical, drop anything else.
        df = df.rename(columns=CSV_COLUMN_MAP)[CANONICAL_COLUMNS]
        logger.info("Loaded %d rows from %s", len(df), path.name)
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Combined dataset: %d rows across %d file(s)", len(combined), len(paths))
    return combined


def _group_by_sensor(
    df: pd.DataFrame, active_ids: Optional[List[str]]
) -> Dict[str, pd.DataFrame]:
    """Group by sensor_id (sorted by timestamp), optionally filtered."""
    if active_ids is not None:
        df = df[df["sensor_id"].isin(active_ids)]
        if df.empty:
            raise RuntimeError(
                f"No rows match ACTIVE_SENSOR_IDS={active_ids}. "
                "Check the CSV's sensor_id values."
            )

    sensor_dfs: Dict[str, pd.DataFrame] = {}
    for sid, group in df.groupby("sensor_id"):
        ordered = group.sort_values("timestamp").reset_index(drop=True)
        sensor_dfs[str(sid)] = ordered
        logger.info("Sensor %s: %d rows", sid, len(ordered))

    if not sensor_dfs:
        raise RuntimeError("Grouping produced 0 sensors")
    return sensor_dfs


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def _row_to_event(sensor_id: str, row: pd.Series) -> SensorEvent:
    """Build a validated SensorEvent from a canonical-named DataFrame row."""
    return SensorEvent(
        sensor_id=sensor_id,
        timestamp=row["timestamp"],
        # location
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        sensor_radius_km=float(row["sensor_radius_km"]),
        # pollutants
        PM25=float(row["PM25"]),
        PM10=float(row["PM10"]),
        NO2=float(row["NO2"]),
        SO2=float(row["SO2"]),
        CO=float(row["CO"]),
        O3=float(row["O3"]),
        # weather
        temperature_2m=float(row["temperature_2m"]),
        relative_humidity_2m=float(row["relative_humidity_2m"]),
        wind_speed_10m=float(row["wind_speed_10m"]),
        wind_direction_10m=float(row["wind_direction_10m"]),
    )


async def _publish_tick(
    producer: AIOKafkaProducer,
    sensor_dfs: Dict[str, pd.DataFrame],
    row_idx: int,
    tick_num: int,
) -> None:
    """Publish one message per active sensor for the given row index."""
    published = 0
    validation_errors = 0
    kafka_errors = 0

    for sensor_id, df in sensor_dfs.items():
        if row_idx >= len(df):
            # This sensor has fewer rows than the tick — skip silently.
            continue
        row = df.iloc[row_idx]

        try:
            event = _row_to_event(sensor_id, row)
        except ValidationError as e:
            validation_errors += 1
            logger.warning(
                "Skipping invalid row sensor=%s row_idx=%d errors=%s",
                sensor_id,
                row_idx,
                e.errors(include_url=False),
            )
            continue
        except (KeyError, ValueError, TypeError) as e:
            validation_errors += 1
            logger.warning(
                "Skipping unparseable row sensor=%s row_idx=%d err=%s",
                sensor_id,
                row_idx,
                e,
            )
            continue

        try:
            await producer.send_and_wait(
                topic=settings.KAFKA_TOPIC_SENSOR_RAW,
                value=event.to_message(),
                key=event.sensor_id,
            )
            published += 1
        except Exception as e:
            kafka_errors += 1
            logger.error(
                "Kafka publish failed sensor=%s row_idx=%d err=%s",
                sensor_id,
                row_idx,
                e,
            )

    logger.info(
        "Tick %d | row_idx=%d | published=%d validation_errors=%d kafka_errors=%d",
        tick_num,
        row_idx,
        published,
        validation_errors,
        kafka_errors,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_producer() -> None:
    csv_dir = Path(settings.CSV_DATA_PATH)
    active_ids = settings.active_sensor_ids

    logger.info(
        "Producer starting | csv_dir=%s | active_sensors=%s | "
        "tick=%ds | topic=%s | loop_on_eof=%s",
        csv_dir,
        active_ids or "ALL",
        settings.SIMULATION_TICK_SECONDS,
        settings.KAFKA_TOPIC_SENSOR_RAW,
        settings.PRODUCER_LOOP_ON_EOF,
    )

    raw_df = _load_all_csvs(csv_dir)
    sensor_dfs = _group_by_sensor(raw_df, active_ids)

    # Simulation advances row-by-row; longest sensor history sets the limit.
    max_rows = max(len(df) for df in sensor_dfs.values())
    logger.info(
        "Simulation length: up to %d ticks (max rows across %d sensor(s))",
        max_rows,
        len(sensor_dfs),
    )

    producer = await get_producer()

    # Graceful shutdown.
    stop_event = asyncio.Event()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received — finishing current tick and stopping")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Windows: not supported via loop; KeyboardInterrupt still works.
            pass

    tick_num = 0
    row_idx = 0
    try:
        while not stop_event.is_set():
            tick_num += 1
            await _publish_tick(producer, sensor_dfs, row_idx, tick_num)

            row_idx += 1
            if row_idx >= max_rows:
                if settings.PRODUCER_LOOP_ON_EOF:
                    logger.info(
                        "Dataset exhausted after %d ticks — looping back to row 0",
                        tick_num,
                    )
                    row_idx = 0
                else:
                    logger.info("Dataset exhausted after %d ticks — stopping", tick_num)
                    break

            # Sleep, but wake early on shutdown.
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.SIMULATION_TICK_SECONDS,
                )
                break  # stop_event fired
            except asyncio.TimeoutError:
                pass
    finally:
        await producer.stop()
        logger.info("Producer stopped cleanly after %d tick(s)", tick_num)


if __name__ == "__main__":
    try:
        asyncio.run(run_producer())
    except KeyboardInterrupt:
        pass
