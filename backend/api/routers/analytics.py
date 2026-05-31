"""
Analytics router — DuckDB queries over the Parquet lakehouse.

All endpoints are read-only and computed at request time. The lakehouse is
populated independently by `consumers/lakehouse_writer.py`; if that
consumer is down, these endpoints return empty results, NOT an error.

Each handler wraps the sync DuckDB call in `asyncio.to_thread` so the
FastAPI event loop stays free.
"""

import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from core.config import settings
from core.logger import get_logger
from lakehouse.query_engine import LakehouseQueryEngine

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Module-level singleton — DuckDB connection is per-call so this is just a
# tiny wrapper holding the Parquet root path.
_engine = LakehouseQueryEngine(Path(settings.LAKEHOUSE_PATH))


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TrendPoint(BaseModel):
    timestamp: str
    aqi: int


class TrendResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sensor_id: str
    range: str
    points: List[TrendPoint]
    avg_aqi: Optional[float]
    peak_aqi: Optional[int]
    worst_day: Optional[str]


class DailySummaryEntry(BaseModel):
    date: str
    day_name: str
    avg_aqi: int
    aqi_category: str


class WorstDayResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    days: int
    worst_day: Optional[str]
    worst_day_date: Optional[str]
    worst_day_aqi: Optional[int]
    worst_day_category: Optional[str] = None
    daily_summary: List[DailySummaryEntry]


class SensorComparisonEntry(BaseModel):
    sensor_id: str
    avg_aqi: int
    aqi_category: str
    n_samples: int


class SensorComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    range: str
    sensors: List[SensorComparisonEntry]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/trend",
    response_model=TrendResponse,
    summary="Hourly AQI trend for a sensor over the last N hours of event time",
)
async def get_trend(
    sensor_id: str = Query(..., min_length=1),
    hours: int = Query(48, ge=1, le=720),
) -> TrendResponse:
    try:
        result = await asyncio.to_thread(_engine.query_trend, sensor_id, hours)
    except Exception as e:
        logger.exception("trend query failed sensor_id=%s hours=%d: %s",
                         sensor_id, hours, e)
        raise HTTPException(status_code=500, detail="Analytics query failed")
    return TrendResponse(**result)


@router.get(
    "/worst-day",
    response_model=WorstDayResponse,
    summary="Worst-AQI day in the last N days",
)
async def get_worst_day(
    days: int = Query(7, ge=1, le=90),
) -> WorstDayResponse:
    try:
        result = await asyncio.to_thread(_engine.query_worst_day, days)
    except Exception as e:
        logger.exception("worst-day query failed days=%d: %s", days, e)
        raise HTTPException(status_code=500, detail="Analytics query failed")
    return WorstDayResponse(**result)


@router.get(
    "/sensor-comparison",
    response_model=SensorComparisonResponse,
    summary="Rank every sensor by average AQI over the last N hours",
)
async def get_sensor_comparison(
    hours: int = Query(24, ge=1, le=168),
) -> SensorComparisonResponse:
    try:
        result = await asyncio.to_thread(_engine.query_sensor_comparison, hours)
    except Exception as e:
        logger.exception("sensor-comparison query failed hours=%d: %s",
                         hours, e)
        raise HTTPException(status_code=500, detail="Analytics query failed")
    return SensorComparisonResponse(**result)
