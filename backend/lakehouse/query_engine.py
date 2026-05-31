"""
DuckDB-backed analytics over the Parquet lakehouse.

All queries read from the directory of date-partitioned Parquet files
written by `lakehouse.writer.LakehouseBatchWriter`. AQI is computed
on-the-fly using the EXACT same `aqi_service` functions the real-time
consumer uses — there is one source of truth for the AQI formula.

DuckDB connections are short-lived (opened per query) because:
  - DuckDB is embedded and connection setup is microseconds-cheap.
  - We never hold mutable state in the engine.
  - The Parquet directory is discovered fresh on every call, so newly-
    written files are visible immediately.

All public methods are SYNC. The FastAPI router wraps them with
`asyncio.to_thread` so DuckDB never blocks the event loop.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from core.logger import get_logger
from services.aqi_service import (
    compute_overall_aqi,
    compute_sub_index,
    get_aqi_category,
)
from streaming.schemas import POLLUTANT_COLUMNS

logger = get_logger(__name__)


# Columns we need from Parquet for any AQI-aware analytics.
_POLLUTANT_SELECT = ", ".join(POLLUTANT_COLUMNS)


class LakehouseQueryEngine:
    """DuckDB queries over the bronze Parquet directory."""

    def __init__(self, root_path: Path) -> None:
        self.root_path = Path(root_path).resolve()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _has_data(self) -> bool:
        """True if the lakehouse directory contains at least one Parquet file."""
        if not self.root_path.exists():
            return False
        return any(self.root_path.rglob("*.parquet"))

    def _glob(self) -> str:
        """Recursive Parquet glob, forward-slashed (DuckDB doesn't like '\\')."""
        return str(self.root_path / "**" / "*.parquet").replace("\\", "/")

    def _connect(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(":memory:")
        # Register a single view over the whole Hive-partitioned dataset.
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW lake AS
            SELECT * FROM read_parquet('{self._glob()}', hive_partitioning=1)
            """
        )
        return conn

    @staticmethod
    def _row_aqi(row: Dict[str, Any]) -> Optional[int]:
        """Compute overall AQI from one Parquet row's pollutant columns."""
        sub = {p: compute_sub_index(p, row.get(p)) for p in POLLUTANT_COLUMNS}
        if any(v is None for v in sub.values()):
            return None
        aqi, _ = compute_overall_aqi(sub)
        return aqi

    def _max_timestamp(self, conn, sensor_id: Optional[str] = None) -> Optional[datetime]:
        if sensor_id:
            row = conn.execute(
                "SELECT MAX(timestamp) AS ts FROM lake WHERE sensor_id = ?",
                [sensor_id],
            ).fetchone()
        else:
            row = conn.execute("SELECT MAX(timestamp) AS ts FROM lake").fetchone()
        return row[0] if row and row[0] else None

    # ------------------------------------------------------------------
    # Public analytics queries
    # ------------------------------------------------------------------

    def query_trend(self, sensor_id: str, hours: int) -> Dict[str, Any]:
        """Hourly AQI trend for a sensor over the last `hours` of EVENT time.

        Returns: { sensor_id, range, points: [{timestamp, aqi}], avg_aqi,
                   peak_aqi, worst_day }.
        Empty points list if no data.
        """
        result_empty = {
            "sensor_id": sensor_id,
            "range": f"{hours}h",
            "points": [],
            "avg_aqi": None,
            "peak_aqi": None,
            "worst_day": None,
        }
        if not self._has_data():
            return result_empty

        conn = self._connect()
        try:
            max_ts = self._max_timestamp(conn, sensor_id)
            if not max_ts:
                return result_empty
            cutoff = max_ts - timedelta(hours=hours)

            rows = conn.execute(
                f"""
                SELECT timestamp, {_POLLUTANT_SELECT}
                FROM lake
                WHERE sensor_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                [sensor_id, cutoff],
            ).fetchall()
            cols = [d[0] for d in conn.description]
        finally:
            conn.close()

        points: List[dict] = []
        per_day_aqi: Dict[str, List[int]] = {}
        for r in rows:
            row = dict(zip(cols, r))
            aqi = self._row_aqi(row)
            if aqi is None:
                continue
            ts: datetime = row["timestamp"]
            points.append({"timestamp": ts.isoformat(), "aqi": aqi})
            per_day_aqi.setdefault(ts.strftime("%A"), []).append(aqi)

        if not points:
            return result_empty

        aqis = [p["aqi"] for p in points]
        worst_day = max(per_day_aqi.items(), key=lambda kv: max(kv[1]))[0]

        return {
            "sensor_id": sensor_id,
            "range": f"{hours}h",
            "points": points,
            "avg_aqi": round(sum(aqis) / len(aqis), 1),
            "peak_aqi": max(aqis),
            "worst_day": worst_day,
        }

    def query_worst_day(self, days: int) -> Dict[str, Any]:
        """Find the worst-AQI day in the last `days` (event-time).

        Aggregates hourly observations to daily means, computes AQI from the
        daily mean pollutants, and reports the highest. Includes a per-day
        summary so the UI can show a small bar chart if desired.
        """
        result_empty = {
            "days": days,
            "worst_day": None,
            "worst_day_date": None,
            "worst_day_aqi": None,
            "daily_summary": [],
        }
        if not self._has_data():
            return result_empty

        conn = self._connect()
        try:
            max_ts = self._max_timestamp(conn)
            if not max_ts:
                return result_empty
            cutoff = max_ts - timedelta(days=days)

            avg_cols = ", ".join(f"AVG({p}) AS {p}" for p in POLLUTANT_COLUMNS)
            rows = conn.execute(
                f"""
                SELECT
                    CAST(timestamp AS DATE) AS day,
                    {avg_cols}
                FROM lake
                WHERE timestamp >= ?
                GROUP BY day
                ORDER BY day ASC
                """,
                [cutoff],
            ).fetchall()
            cols = [d[0] for d in conn.description]
        finally:
            conn.close()

        daily: List[dict] = []
        for r in rows:
            row = dict(zip(cols, r))
            aqi = self._row_aqi(row)
            if aqi is None:
                continue
            day: datetime = row["day"]  # DuckDB returns python date
            daily.append({
                "date": day.isoformat() if hasattr(day, "isoformat") else str(day),
                "day_name": day.strftime("%A") if hasattr(day, "strftime") else "",
                "avg_aqi": aqi,
                "aqi_category": get_aqi_category(aqi),
            })

        if not daily:
            return result_empty

        worst = max(daily, key=lambda d: d["avg_aqi"])
        return {
            "days": days,
            "worst_day": worst["day_name"],
            "worst_day_date": worst["date"],
            "worst_day_aqi": worst["avg_aqi"],
            "worst_day_category": worst["aqi_category"],
            "daily_summary": daily,
        }

    def query_sensor_comparison(self, hours: int = 24) -> Dict[str, Any]:
        """Compare every sensor by average AQI over the last `hours`.

        Returns a list sorted worst-first so the UI can render a ranked bar
        chart directly.
        """
        result_empty = {"range": f"{hours}h", "sensors": []}
        if not self._has_data():
            return result_empty

        conn = self._connect()
        try:
            max_ts = self._max_timestamp(conn)
            if not max_ts:
                return result_empty
            cutoff = max_ts - timedelta(hours=hours)

            avg_cols = ", ".join(f"AVG({p}) AS {p}" for p in POLLUTANT_COLUMNS)
            rows = conn.execute(
                f"""
                SELECT
                    sensor_id,
                    {avg_cols},
                    COUNT(*) AS n_samples
                FROM lake
                WHERE timestamp >= ?
                GROUP BY sensor_id
                ORDER BY sensor_id
                """,
                [cutoff],
            ).fetchall()
            cols = [d[0] for d in conn.description]
        finally:
            conn.close()

        sensors: List[dict] = []
        for r in rows:
            row = dict(zip(cols, r))
            aqi = self._row_aqi(row)
            if aqi is None:
                continue
            sensors.append({
                "sensor_id": row["sensor_id"],
                "avg_aqi": aqi,
                "aqi_category": get_aqi_category(aqi),
                "n_samples": int(row["n_samples"]),
            })

        sensors.sort(key=lambda s: s["avg_aqi"], reverse=True)
        return {"range": f"{hours}h", "sensors": sensors}
