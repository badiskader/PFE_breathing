"""
AQI router. Read-only.

GET /aqi/current?sensor_id=X — latest AQI for one sensor.
GET /aqi/sensors             — latest AQI for every sensor (dashboard cards).

The response is the JOIN of:
  - latest `aqi_results` doc per sensor (AQI score + sub-indices + category)
  - latest `sensor_readings` doc per sensor (location + raw pollutants + weather)

Both collections are indexed by (sensor_id, timestamp DESC), so the join
is two cheap lookups per sensor.

No computation at request time.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict

from api.dependencies import (
    get_aqi_collection,
    get_sensor_readings_collection,
)
from core.logger import get_logger
from streaming.schemas import POLLUTANT_COLUMNS, WEATHER_COLUMNS

logger = get_logger(__name__)

router = APIRouter(prefix="/aqi", tags=["aqi"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class WeatherBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    temperature_2m: Optional[float] = None
    relative_humidity_2m: Optional[float] = None
    wind_speed_10m: Optional[float] = None
    wind_direction_10m: Optional[float] = None


class AQIResultResponse(BaseModel):
    """Enriched AQI result — joins aqi_results with the latest raw observation."""

    model_config = ConfigDict(extra="ignore")

    # From aqi_results
    sensor_id: str
    timestamp: datetime
    aqi_score: int
    aqi_category: str
    risk_level: str
    dominant_pollutant: str
    sub_indices: Dict[str, int]

    # From sensor_readings (joined at request time)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sensor_radius_km: Optional[float] = None
    pollutants: Optional[Dict[str, float]] = None
    weather: Optional[WeatherBlock] = None


class AQISensorsResponse(BaseModel):
    count: int
    sensors: List[AQIResultResponse]


# ---------------------------------------------------------------------------
# Join helpers
# ---------------------------------------------------------------------------

async def _latest_reading(
    sensor_id: str,
    readings_coll: AsyncIOMotorCollection,
) -> Optional[dict]:
    """Latest sensor_readings doc for one sensor (or None if no data)."""
    return await readings_coll.find_one(
        {"sensor_id": sensor_id},
        sort=[("timestamp", -1)],
        projection={"_id": 0},
    )


async def _latest_readings_by_sensor(
    readings_coll: AsyncIOMotorCollection,
) -> Dict[str, dict]:
    """One aggregation: {sensor_id: latest sensor_readings doc}."""
    pipeline = [
        {"$sort": {"sensor_id": 1, "timestamp": -1}},
        {"$group": {"_id": "$sensor_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0}},
    ]
    docs = await readings_coll.aggregate(pipeline).to_list(length=None)
    return {d["sensor_id"]: d for d in docs}


def _merge(
    aqi_doc: dict,
    reading: Optional[dict],
) -> AQIResultResponse:
    """Combine one aqi_results doc + one sensor_readings doc into the response."""
    enriched: Dict[str, Any] = dict(aqi_doc)

    if reading:
        enriched["latitude"] = reading.get("latitude")
        enriched["longitude"] = reading.get("longitude")
        enriched["sensor_radius_km"] = reading.get("sensor_radius_km")
        enriched["pollutants"] = {
            p: reading[p] for p in POLLUTANT_COLUMNS if p in reading
        }
        weather = {w: reading[w] for w in WEATHER_COLUMNS if w in reading}
        enriched["weather"] = WeatherBlock(**weather) if weather else None

    return AQIResultResponse(**enriched)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/current",
    response_model=AQIResultResponse,
    summary="Latest AQI for one sensor (joined with location + pollutants + weather)",
)
async def get_current_aqi(
    sensor_id: str = Query(..., min_length=1, description="Sensor identifier"),
    aqi_coll: AsyncIOMotorCollection = Depends(get_aqi_collection),
    readings_coll: AsyncIOMotorCollection = Depends(get_sensor_readings_collection),
) -> AQIResultResponse:
    aqi_doc = await aqi_coll.find_one(
        {"sensor_id": sensor_id},
        sort=[("timestamp", -1)],
        projection={"_id": 0},
    )
    if aqi_doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"No AQI result yet for sensor_id={sensor_id}",
        )

    reading = await _latest_reading(sensor_id, readings_coll)
    return _merge(aqi_doc, reading)


@router.get(
    "/sensors",
    response_model=AQISensorsResponse,
    summary="Latest AQI for every active sensor (dashboard cards)",
)
async def list_sensors(
    aqi_coll: AsyncIOMotorCollection = Depends(get_aqi_collection),
    readings_coll: AsyncIOMotorCollection = Depends(get_sensor_readings_collection),
) -> AQISensorsResponse:
    # One pass for latest AQI per sensor.
    pipeline = [
        {"$sort": {"sensor_id": 1, "timestamp": -1}},
        {"$group": {"_id": "$sensor_id", "latest": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$latest"}},
        {"$project": {"_id": 0}},
        {"$sort": {"sensor_id": 1}},
    ]
    aqi_docs = await aqi_coll.aggregate(pipeline).to_list(length=None)

    # One pass for latest reading per sensor.
    readings_by_sensor = await _latest_readings_by_sensor(readings_coll)

    sensors = [
        _merge(aqi_doc, readings_by_sensor.get(aqi_doc["sensor_id"]))
        for aqi_doc in aqi_docs
    ]
    return AQISensorsResponse(count=len(sensors), sensors=sensors)
