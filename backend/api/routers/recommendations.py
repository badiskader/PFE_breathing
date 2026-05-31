"""
Recommendations router (Type 1 — dashboard). Read-only.

GET /recommendations/dashboard?user_id=X&sensor_id=Y
  1. Look up user → vulnerability_category.
  2. Look up pre-generated dashboard_recommendation for (sensor_id, category).
  3. Return.

NO LLM call here. NO rule recomputation. Pure lookup.
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict

from api.dependencies import (
    get_current_user_id,
    get_dashboard_recommendations_collection,
    get_users_collection,
)
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class RuleOutputResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vulnerability_category: str
    forecast_aqi_max: int
    forecast_category: str
    aqi_trajectory: str
    flagged_pollutants: List[str]
    urgency_level: str
    key_risks: List[str]
    pollutant_scores: Dict[str, int]
    pollutant_max_values: Dict[str, float]


class DashboardRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sensor_id: str
    vulnerability_category: str
    generated_at: datetime
    forecast_aqi_max: int
    forecast_category: str
    rule_output: RuleOutputResponse
    recommendation_text: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    response_model=DashboardRecommendationResponse,
    summary="Pre-computed Type 1 recommendation for the user's nearest sensor",
)
async def get_dashboard_recommendation(
    sensor_id: str = Query(..., min_length=1),
    user_id: str = Depends(get_current_user_id),
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
    reco_coll: AsyncIOMotorCollection = Depends(
        get_dashboard_recommendations_collection
    ),
) -> DashboardRecommendationResponse:
    # 1. Fetch user → vulnerability_category.
    user = await users_coll.find_one(
        {"user_id": user_id},
        projection={"_id": 0, "vulnerability_category": 1},
    )
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    category = user.get("vulnerability_category")
    if not category:
        raise HTTPException(
            status_code=409,
            detail=(
                f"User {user_id} has no vulnerability_category — call "
                f"POST /users/onboarding first."
            ),
        )

    # 2. Fetch pre-generated recommendation.
    reco: Dict[str, Any] | None = await reco_coll.find_one(
        {"sensor_id": sensor_id, "vulnerability_category": category},
        projection={"_id": 0},
    )
    if reco is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No pre-generated recommendation for sensor_id={sensor_id}, "
                f"category={category}. The recommendation scheduler may not "
                f"have produced one yet."
            ),
        )

    return DashboardRecommendationResponse(**reco)
