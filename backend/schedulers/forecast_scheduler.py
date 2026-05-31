"""
Forecast scheduler.

Every `FORECAST_SCHEDULER_INTERVAL_SECONDS` (= 1 simulated hour):
  1. Discover active sensors (env-driven or from MongoDB).
  2. For each sensor: fetch last FORECAST_WINDOW_SIZE records.
     Skip sensors with insufficient history.
  3. Build Mamba payload (full raw records, no preprocessing).
  4. Call Mamba API.
  5. Parse forecast → canonical hourly dicts.
  6. Compute predicted AQI for each hour via aqi_service.
  7. Upsert one document per sensor into `predictions`.

The scheduler is thin. Mamba I/O lives in `services/forecast_service.py`;
AQI math lives in `services/aqi_service.py`. This module only orchestrates.

The function `run_forecast_cycle()` is the entry point that FastAPI will
later register with APScheduler (Step 6+). The `__main__` block lets us
run the scheduler as a standalone process for testing in this step.
"""

import asyncio
import signal
from datetime import datetime, timezone
from typing import List

from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from core.config import settings
from core.logger import get_logger
from core.mongo_client import (
    close_mongo_connection,
    connect_to_mongo,
    ensure_predictions_indexes,
    predictions,
    sensor_readings,
)
from services.aqi_service import AQIComputationError, compute_aqi_from_pollutants
from services.forecast_service import (
    ForecastError,
    ForecastedHour,
    InsufficientHistoryError,
    PredictionDocument,
    build_mamba_payload,
    call_mamba_api,
    fetch_sensor_history,
    parse_forecast_response,
)
from streaming.schemas import POLLUTANT_COLUMNS

logger = get_logger(__name__)


def _utc_now_naive() -> datetime:
    """Naive UTC `datetime` — matches the rest of the timestamp convention."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Active-sensor discovery
# ---------------------------------------------------------------------------

async def _discover_active_sensors() -> List[str]:
    """Return the list of sensor_ids to forecast.

    Priority:
      1. `ACTIVE_SENSOR_IDS` env var (explicit subset for development).
      2. distinct sensor_ids found in `sensor_readings`.
    """
    if settings.active_sensor_ids:
        return settings.active_sensor_ids
    return sorted(await sensor_readings().distinct("sensor_id"))


# ---------------------------------------------------------------------------
# AQI enrichment for forecasted hours
# ---------------------------------------------------------------------------

def _enrich_with_aqi(forecast_hours: List[dict]) -> List[ForecastedHour]:
    """Attach predicted_aqi + predicted_category to each forecast hour."""
    enriched: List[ForecastedHour] = []
    for hour in forecast_hours:
        pollutants = {p: float(hour[p]) for p in POLLUTANT_COLUMNS}
        try:
            components = compute_aqi_from_pollutants(pollutants)
        except AQIComputationError as e:
            logger.warning(
                "Skipping forecast hour (cannot compute AQI): hour_offset=%s err=%s",
                hour.get("hour_offset"),
                e,
            )
            continue
        enriched.append(
            ForecastedHour(
                hour_offset=int(hour["hour_offset"]),
                timestamp=hour["timestamp"],
                PM25=pollutants["PM25"],
                PM10=pollutants["PM10"],
                NO2=pollutants["NO2"],
                SO2=pollutants["SO2"],
                CO=pollutants["CO"],
                O3=pollutants["O3"],
                predicted_aqi=int(components["aqi_score"]),       # type: ignore[arg-type]
                predicted_category=str(components["aqi_category"]),
            )
        )
    return enriched


# ---------------------------------------------------------------------------
# One sensor's forecast — sequential today, easy to batch tomorrow
# ---------------------------------------------------------------------------

async def _forecast_one_sensor(sensor_id: str) -> PredictionDocument:
    """Run the full forecast pipeline for a single sensor.

    Sequential calls are used today. The forecast_service API already
    accepts a list-of-sensors payload, so switching to batch later requires
    only this function to be rewritten — call_mamba_api and parse_forecast_response
    do not change.
    """
    history = await fetch_sensor_history(sensor_id, settings.FORECAST_WINDOW_SIZE)
    last_timestamp: datetime = history[-1]["timestamp"]

    payload = build_mamba_payload([history])
    response = await call_mamba_api(payload)
    parsed = parse_forecast_response(response, [last_timestamp])

    if not parsed or not parsed[0]:
        raise ForecastError(f"Empty forecast for sensor_id={sensor_id}")

    enriched_hours = _enrich_with_aqi(parsed[0])
    if not enriched_hours:
        raise ForecastError(
            f"All forecast hours dropped during AQI enrichment for {sensor_id}"
        )

    return PredictionDocument(
        sensor_id=sensor_id,
        generated_at=_utc_now_naive(),
        forecast_horizon_hours=settings.FORECAST_HORIZON_HOURS,
        predictions=enriched_hours,
    )


# ---------------------------------------------------------------------------
# Cycle — the entry point that FastAPI will hand to APScheduler in Step 6+
# ---------------------------------------------------------------------------

async def run_forecast_cycle() -> dict:
    """Execute one full forecast cycle across all active sensors.

    Returns a metrics dict (useful for tests and future health endpoints).
    """
    started = _utc_now_naive()
    active = await _discover_active_sensors()
    logger.info("Forecast cycle starting | active_sensors=%d", len(active))

    metrics = {
        "total": len(active),
        "succeeded": 0,
        "skipped_insufficient_history": 0,
        "failed": 0,
    }

    ops: List[UpdateOne] = []
    for sensor_id in active:
        try:
            doc_model = await _forecast_one_sensor(sensor_id)
        except InsufficientHistoryError as e:
            metrics["skipped_insufficient_history"] += 1
            logger.info("Skipping sensor: %s", e)
            continue
        except ForecastError as e:
            metrics["failed"] += 1
            logger.error("Forecast failed sensor=%s err=%s", sensor_id, e)
            continue
        except Exception as e:  # never crash the scheduler on one sensor
            metrics["failed"] += 1
            logger.exception(
                "Unexpected forecast error sensor=%s err=%s", sensor_id, e
            )
            continue

        ops.append(
            UpdateOne(
                {"sensor_id": sensor_id},
                {"$set": doc_model.to_doc()},
                upsert=True,
            )
        )
        metrics["succeeded"] += 1

    if ops:
        try:
            await predictions().bulk_write(ops, ordered=False)
        except BulkWriteError as bwe:
            logger.error(
                "Predictions bulk_write failed: %s",
                (bwe.details or {}).get("writeErrors"),
            )

    duration = (_utc_now_naive() - started).total_seconds()
    logger.info(
        "Forecast cycle complete | total=%d succeeded=%d "
        "skipped_no_history=%d failed=%d duration=%.2fs",
        metrics["total"],
        metrics["succeeded"],
        metrics["skipped_insufficient_history"],
        metrics["failed"],
        duration,
    )
    return metrics


# ---------------------------------------------------------------------------
# Standalone runner — for testing in this step (before FastAPI exists)
# ---------------------------------------------------------------------------

async def _standalone_main() -> None:
    await connect_to_mongo()
    await ensure_predictions_indexes()

    stop_event = asyncio.Event()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    interval = settings.FORECAST_SCHEDULER_INTERVAL_SECONDS
    logger.info(
        "Forecast scheduler standalone | interval=%ds | mamba_url=%s | "
        "window=%d | horizon=%d",
        interval,
        settings.MAMBA_API_URL,
        settings.FORECAST_WINDOW_SIZE,
        settings.FORECAST_HORIZON_HOURS,
    )

    try:
        while not stop_event.is_set():
            try:
                await run_forecast_cycle()
            except Exception as e:
                logger.exception("Forecast cycle crashed (continuing): %s", e)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break  # stop_event fired
            except asyncio.TimeoutError:
                pass
    finally:
        await close_mongo_connection()
        logger.info("Forecast scheduler stopped")


if __name__ == "__main__":
    try:
        asyncio.run(_standalone_main())
    except KeyboardInterrupt:
        pass
