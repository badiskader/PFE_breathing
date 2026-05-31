"""
Predictions router. Read-only.

GET /predictions?sensor_id=X — latest 12-hour forecast for one sensor.
Served by the unique index on sensor_id in `predictions`.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict

from api.dependencies import get_predictions_collection
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/predictions", tags=["predictions"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ForecastedHourResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

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


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sensor_id: str
    generated_at: datetime
    forecast_horizon_hours: int
    predictions: List[ForecastedHourResponse]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PredictionResponse,
    summary="Latest 12-hour forecast for one sensor",
)
async def get_predictions(
    sensor_id: str = Query(..., min_length=1),
    coll: AsyncIOMotorCollection = Depends(get_predictions_collection),
) -> PredictionResponse:
    doc = await coll.find_one(
        {"sensor_id": sensor_id},
        projection={"_id": 0},
    )
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast yet for sensor_id={sensor_id}",
        )
    return PredictionResponse(**doc)
