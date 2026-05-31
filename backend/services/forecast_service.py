"""
Forecast service — Mamba API integration.

Owns:
  * the ONLY field-name mapping between the canonical schema and Mamba's
    external naming (`pm2_5`, `nitrogen_dioxide`, `center_latitude`, …)
  * the HTTP client wrapped around POST /predict_raw
  * payload assembly (FULL raw records, NO preprocessing of any kind)
  * response parsing back into canonical names
  * the Pydantic persistence model for the `predictions` collection

Architectural rule
------------------
The backend does NOT transform, scale, normalize, encode, or engineer
features. Mamba performs all of that internally. We send raw values
verbatim and we receive forecasted pollutant concentrations verbatim.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import httpx
from pydantic import BaseModel, ConfigDict

from core.config import settings
from core.logger import get_logger
from core.mongo_client import sensor_readings
from streaming.schemas import POLLUTANT_COLUMNS

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Field-name mappings — the ONLY place Mamba's external naming touches the code
# ---------------------------------------------------------------------------

# Canonical (Mongo) → Mamba (API) field names.
# Order is preserved so each outgoing record has a stable key order.
CANONICAL_TO_MAMBA: Dict[str, str] = {
    # identity & time
    "sensor_id":            "sensor_id",
    "timestamp":            "time",
    # location
    "latitude":             "center_latitude",
    "longitude":            "center_longitude",
    "sensor_radius_km":     "sensor_radius_km",
    # pollutants
    "PM10":                 "pm10",
    "PM25":                 "pm2_5",
    "NO2":                  "nitrogen_dioxide",
    "O3":                   "ozone",
    "CO":                   "carbon_monoxide",
    "SO2":                  "sulphur_dioxide",
    # weather
    "temperature_2m":       "temperature_2m",
    "relative_humidity_2m": "relative_humidity_2m",
    "wind_speed_10m":       "wind_speed_10m",
    "wind_direction_10m":   "wind_direction_10m",
}

# Inverse mapping for parsing Mamba's response (response carries only pollutants).
MAMBA_TO_CANONICAL_POLLUTANT: Dict[str, str] = {
    "pm10":             "PM10",
    "pm2_5":            "PM25",
    "nitrogen_dioxide": "NO2",
    "sulphur_dioxide":  "SO2",
    "carbon_monoxide":  "CO",
    "ozone":            "O3",
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ForecastError(Exception):
    """Generic forecast failure (HTTP, validation, parsing)."""


class InsufficientHistoryError(ForecastError):
    """Sensor doesn't have FORECAST_WINDOW_SIZE records yet."""


# ---------------------------------------------------------------------------
# Persistence model (MongoDB `predictions` collection)
# ---------------------------------------------------------------------------

class ForecastedHour(BaseModel):
    """One forecasted hour, canonical naming, AQI enrichment included."""

    model_config = ConfigDict(extra="forbid")

    hour_offset: int
    timestamp: datetime

    PM25: float
    PM10: float
    NO2: float
    SO2: float
    CO: float
    O3: float

    predicted_aqi: int
    predicted_category: str


class PredictionDocument(BaseModel):
    """One forecast cycle's output for one sensor (upserted per sensor)."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str
    generated_at: datetime
    forecast_horizon_hours: int
    predictions: List[ForecastedHour]

    def to_doc(self) -> dict:
        return self.model_dump(mode="python")


# ---------------------------------------------------------------------------
# 1. Fetch history from MongoDB
# ---------------------------------------------------------------------------

async def fetch_sensor_history(sensor_id: str, window_size: int) -> List[dict]:
    """Fetch the last `window_size` raw records for `sensor_id`, ordered
    OLDEST → NEWEST (the order Mamba expects).

    Returns:
        List of canonical documents (full 14-field shape, `_id` stripped).

    Raises:
        InsufficientHistoryError: if fewer than `window_size` records exist.
    """
    coll = sensor_readings()
    cursor = (
        coll.find({"sensor_id": sensor_id}, projection={"_id": 0})
        .sort("timestamp", -1)
        .limit(window_size)
    )
    docs = await cursor.to_list(length=window_size)

    if len(docs) < window_size:
        raise InsufficientHistoryError(
            f"sensor_id={sensor_id}: have {len(docs)}/{window_size} records"
        )

    # Mongo returned newest first; reverse to oldest first.
    docs.reverse()
    return docs


# ---------------------------------------------------------------------------
# 2. Build Mamba request payload — pure field-name translation, no math
# ---------------------------------------------------------------------------

def _canonical_to_mamba_record(doc: dict) -> dict:
    """Translate one canonical document → Mamba record (rename keys, ISO time)."""
    record: Dict[str, object] = {}
    for canonical_key, mamba_key in CANONICAL_TO_MAMBA.items():
        value = doc.get(canonical_key)
        if isinstance(value, datetime):
            value = value.isoformat()
        record[mamba_key] = value
    return record


def build_mamba_payload(sensor_histories: List[List[dict]]) -> dict:
    """Assemble the full request body for POST /predict_raw.

    Args:
        sensor_histories: parallel list of histories, one per sensor.
            Each history is exactly FORECAST_WINDOW_SIZE canonical documents
            (oldest → newest).

    Returns:
        { "sensor_data": [ [record, ...], [record, ...], ... ] }
    """
    sensor_data = []
    for history in sensor_histories:
        if len(history) != settings.FORECAST_WINDOW_SIZE:
            raise ForecastError(
                f"Each sensor must carry exactly {settings.FORECAST_WINDOW_SIZE} "
                f"records (got {len(history)})"
            )
        sensor_data.append([_canonical_to_mamba_record(d) for d in history])

    return {"sensor_data": sensor_data}


# ---------------------------------------------------------------------------
# 3. HTTP call to Mamba
# ---------------------------------------------------------------------------

async def call_mamba_api(payload: dict) -> dict:
    """POST `payload` to the Mamba `/predict_raw` endpoint. Return parsed JSON.

    The same AsyncClient lifecycle (open → request → close) is used per call.
    For higher throughput later, callers can switch to a shared client; the
    function signature won't change.
    """
    url = settings.MAMBA_API_URL
    timeout = settings.MAMBA_API_TIMEOUT_SECONDS

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.RequestError as e:
            raise ForecastError(
                f"Mamba HTTP request failed (url={url}): {e}"
            ) from e

    if resp.status_code != 200:
        raise ForecastError(
            f"Mamba returned HTTP {resp.status_code} (url={url}): {resp.text[:500]}"
        )

    try:
        return resp.json()
    except ValueError as e:
        raise ForecastError(f"Mamba response is not valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# 4. Parse Mamba response — translate keys back to canonical, derive timestamps
# ---------------------------------------------------------------------------

def parse_forecast_response(
    response: dict,
    last_timestamps: List[datetime],
) -> List[List[Dict[str, object]]]:
    """Translate Mamba's response into canonical-named hourly dicts.

    Args:
        response: Mamba's JSON body.
        last_timestamps: Per sensor (in payload order), the timestamp of the
            most recent input record. Each forecasted hour's wall-clock
            timestamp = last_timestamp + (hour_offset) hours.

    Returns:
        Parallel list of forecast-hour dicts per sensor, each containing:
            hour_offset, timestamp, PM25, PM10, NO2, SO2, CO, O3

        AQI enrichment is added later by the scheduler (separation of concerns:
        this service is API-bound; AQI lives in aqi_service).
    """
    if "predictions" not in response:
        raise ForecastError("Mamba response missing 'predictions' key")

    sensor_predictions = response["predictions"]
    if not isinstance(sensor_predictions, list):
        raise ForecastError("Mamba response 'predictions' is not a list")
    if len(sensor_predictions) != len(last_timestamps):
        raise ForecastError(
            f"Mamba returned {len(sensor_predictions)} sensor forecasts, "
            f"expected {len(last_timestamps)}"
        )

    parsed: List[List[Dict[str, object]]] = []
    for hours, last_ts in zip(sensor_predictions, last_timestamps):
        if not isinstance(hours, list):
            raise ForecastError("Per-sensor forecast block is not a list")

        sensor_hours: List[Dict[str, object]] = []
        for hour in hours:
            if "hour_offset" not in hour:
                raise ForecastError("Forecast hour missing 'hour_offset'")
            hour_offset = int(hour["hour_offset"])
            row: Dict[str, object] = {
                "hour_offset": hour_offset,
                "timestamp": last_ts + timedelta(hours=hour_offset),
            }
            for mamba_field, canonical_field in MAMBA_TO_CANONICAL_POLLUTANT.items():
                if mamba_field not in hour:
                    raise ForecastError(
                        f"Forecast hour missing field '{mamba_field}'"
                    )
                row[canonical_field] = float(hour[mamba_field])
            # Sanity: every canonical pollutant must end up populated.
            missing = [p for p in POLLUTANT_COLUMNS if p not in row]
            if missing:
                raise ForecastError(f"Parsed hour missing canonical fields: {missing}")
            sensor_hours.append(row)
        parsed.append(sensor_hours)

    return parsed
