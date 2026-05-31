"""
Buffered Parquet writer for the lakehouse bronze layer.

Layout (Hive-style partitioning):
    data/lakehouse/
        date=2025-01-15/
            batch_<uuid12>.parquet
            batch_<uuid12>.parquet
        date=2025-01-16/
            batch_<uuid12>.parquet
        ...

You can't truly append to a single Parquet file — Hive-style partitioning is
the idiomatic substitute. Each flush writes one NEW file per date encountered
in the buffer; DuckDB reads the whole directory as one logical dataset via
`read_parquet(... , hive_partitioning=1)`.

Schema (15 cols, matching the canonical SensorEvent):
  sensor_id, timestamp, latitude, longitude, sensor_radius_km,
  PM25, PM10, NO2, SO2, CO, O3,
  temperature_2m, relative_humidity_2m, wind_speed_10m, wind_direction_10m

The Hive partition column `date` is encoded in the path and is NOT a column
inside the Parquet file (DuckDB reconstructs it on read).
"""

import time
import uuid
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from core.logger import get_logger
from streaming.schemas import SensorEvent

logger = get_logger(__name__)


class LakehouseBatchWriter:
    """In-memory buffer that flushes to date-partitioned Parquet files."""

    def __init__(
        self,
        root_path: Path,
        max_batch_size: int = 200,
        max_age_seconds: float = 30.0,
    ) -> None:
        self.root_path = Path(root_path)
        self.max_batch_size = max_batch_size
        self.max_age_seconds = max_age_seconds
        self._buffer: List[dict] = []
        self._last_flush = time.monotonic()
        self.root_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, event: SensorEvent) -> None:
        """Add one validated event to the buffer (datetime stays native)."""
        self._buffer.append(event.model_dump(mode="python"))

    def __len__(self) -> int:
        return len(self._buffer)

    def should_flush(self) -> bool:
        if not self._buffer:
            return False
        if len(self._buffer) >= self.max_batch_size:
            return True
        if (time.monotonic() - self._last_flush) >= self.max_age_seconds:
            return True
        return False

    def flush(self) -> int:
        """Flush all buffered rows to Parquet. Returns row count written."""
        if not self._buffer:
            return 0

        df = pd.DataFrame(self._buffer)
        # Ensure datetime dtype (it may already be one, but be defensive).
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False, errors="coerce")
        df = df.dropna(subset=["timestamp"])
        if df.empty:
            self._buffer.clear()
            self._last_flush = time.monotonic()
            return 0

        # Partition key column — encoded in the directory name, not in the file.
        df["_event_date"] = df["timestamp"].dt.strftime("%Y-%m-%d")

        total_written = 0
        for date_str, group in df.groupby("_event_date"):
            partition_dir = self.root_path / f"date={date_str}"
            partition_dir.mkdir(parents=True, exist_ok=True)

            filename = f"batch_{uuid.uuid4().hex[:12]}.parquet"
            path = partition_dir / filename

            group_clean = group.drop(columns=["_event_date"])
            table = pa.Table.from_pandas(group_clean, preserve_index=False)
            pq.write_table(table, path, compression="snappy")
            total_written += len(group_clean)

            logger.info(
                "Lakehouse flush | rows=%d → %s",
                len(group_clean),
                path.relative_to(self.root_path),
            )

        self._buffer.clear()
        self._last_flush = time.monotonic()
        return total_written
