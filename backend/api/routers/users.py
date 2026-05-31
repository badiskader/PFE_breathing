"""
Users router.

  GET  /users/me           — return the authenticated user's profile + category
  POST /users/onboarding   — fill / update the authenticated user's health profile
                              and derive vulnerability_category

`user_id` is NO LONGER a request field — it comes from the JWT (`sub` claim).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_current_user_id, get_users_collection
from core.logger import get_logger
from services.recommendation_engine import (
    VULNERABILITY_GENERAL,
    compute_vulnerability_category,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class PreferredLocation(BaseModel):
    name: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class UserOnboardingRequest(BaseModel):
    """Input payload for POST /users/onboarding.

    `user_id` is intentionally NOT here — it's taken from the JWT.
    """
    model_config = ConfigDict(extra="forbid")

    # Identity bits the user may set / update
    name: Optional[str] = Field(default=None, max_length=100)

    # Core profile
    age: int = Field(..., ge=0, le=120)
    gender: Optional[str] = None
    chronic_diseases: List[str] = Field(default_factory=list)
    asthma: bool = False
    cardiovascular: bool = False
    allergies: List[str] = Field(default_factory=list)
    smoking_status: str = "never"        # never / former / current
    activity_level: str = "moderate"     # sedentary / moderate / active
    pollution_sensitivity: str = "low"   # low / medium / high
    preferred_locations: List[PreferredLocation] = Field(default_factory=list)

    # Optional vulnerability inputs
    is_pregnant: Optional[bool] = None
    outdoor_worker: Optional[bool] = None
    intense_sport: Optional[bool] = None
    low_socioeconomic: Optional[bool] = None


class UserOnboardingResponse(BaseModel):
    user_id: str
    vulnerability_category: str
    vulnerability_score: float
    contributing_factors: List[str]
    profile_last_updated: datetime


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    is_guest: bool = False
    vulnerability_category: str = VULNERABILITY_GENERAL
    vulnerability_score: Optional[float] = None
    onboarding_completed: bool = False
    profile: Optional[Dict[str, Any]] = None
    profile_last_updated: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=MeResponse,
    summary="Return the authenticated user's profile",
)
async def me(
    user_id: str = Depends(get_current_user_id),
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
) -> MeResponse:
    doc = await users_coll.find_one(
        {"user_id": user_id},
        projection={"_id": 0, "hashed_password": 0},
    )
    if doc is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return MeResponse(**doc)


@router.post(
    "/onboarding",
    response_model=UserOnboardingResponse,
    summary="Fill or update the authenticated user's health profile",
)
async def onboarding(
    body: UserOnboardingRequest,
    user_id: str = Depends(get_current_user_id),
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
) -> UserOnboardingResponse:
    # Confirm the user exists (guest or registered).
    user = await users_coll.find_one({"user_id": user_id}, projection={"_id": 1})
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"User {user_id} not found. Call POST /auth/guest or "
                f"/auth/register first."
            ),
        )

    profile = body.model_dump(mode="python", exclude={"name"})
    try:
        category, score, factors = compute_vulnerability_category(profile)
    except Exception as e:
        logger.exception("compute_vulnerability_category failed: %s", e)
        raise HTTPException(status_code=500, detail="Profile evaluation failed")

    now = _utc_now_naive()
    set_doc: Dict[str, Any] = {
        "profile": profile,
        "vulnerability_category": category,
        "vulnerability_score": score,
        "vulnerability_factors": factors,
        "onboarding_completed": True,
        "profile_last_updated": now,
    }
    if body.name is not None:
        set_doc["name"] = body.name

    await users_coll.update_one(
        {"user_id": user_id}, {"$set": set_doc}
    )

    logger.info(
        "Onboarding update user_id=%s category=%s score=%.2f factors=%s",
        user_id, category, score, factors,
    )

    return UserOnboardingResponse(
        user_id=user_id,
        vulnerability_category=category,
        vulnerability_score=score,
        contributing_factors=factors,
        profile_last_updated=now,
    )
