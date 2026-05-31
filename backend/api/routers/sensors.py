"""
Sensors router (PUBLIC — no auth required).

GET /sensors  —  list every sensor with its coordinates and detection radius,
                  so the mobile app can compute "nearest sensor" against the
                  user's GPS without needing its own coordinate table.

Coordinates come from `sensor_readings` (the latest doc per sensor wins).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict

from api.dependencies import get_sensor_readings_collection
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sensors", tags=["sensors"])


class SensorMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sensor_id: str
    latitude: float
    longitude: float
    sensor_radius_km: Optional[float] = None
    last_seen: Optional[datetime] = None


class SensorListResponse(BaseModel):
    count: int
    sensors: List[SensorMetadata]


@router.get(
    "",
    response_model=SensorListResponse,
    summary="List every sensor with its location and detection radius",
)
async def list_sensors(
    coll: AsyncIOMotorCollection = Depends(get_sensor_readings_collection),
) -> SensorListResponse:
    pipeline = [
        {"$sort": {"sensor_id": 1, "timestamp": -1}},
        {"$group": {
            "_id": "$sensor_id",
            "latitude": {"$first": "$latitude"},
            "longitude": {"$first": "$longitude"},
            "sensor_radius_km": {"$first": "$sensor_radius_km"},
            "last_seen": {"$first": "$timestamp"},
        }},
        {"$sort": {"_id": 1}},
    ]
    docs = await coll.aggregate(pipeline).to_list(length=None)
    sensors = [
        SensorMetadata(
            sensor_id=d["_id"],
            latitude=d["latitude"],
            longitude=d["longitude"],
            sensor_radius_km=d.get("sensor_radius_km"),
            last_seen=d.get("last_seen"),
        )
        for d in docs
    ]
    return SensorListResponse(count=len(sensors), sensors=sensors)
