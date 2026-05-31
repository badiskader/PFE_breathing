"""
Authentication router.

Three flows:

  POST /auth/register   — email + password + (optional) name → JWT
  POST /auth/login      — email + password → JWT
  POST /auth/guest      — no credentials → JWT (longer-lived)

Guests are first-class users in the database: they get a `user_id` like
`guest_<uuid>` and a default `vulnerability_category="générale"`. This
lets every downstream endpoint treat them uniformly without conditional
logic on `is_guest`.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_users_collection
from core.logger import get_logger
from services.auth_service import (
    create_access_token,
    hash_password,
    verify_password,
)
from services.recommendation_engine import VULNERABILITY_GENERAL

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=6, max_length=200)
    name: Optional[str] = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class GuestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: Optional[str] = Field(default=None, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    is_guest: bool = False
    vulnerability_category: str = VULNERABILITY_GENERAL
    onboarding_completed: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_to_out(doc: Dict[str, Any]) -> UserOut:
    return UserOut(
        user_id=doc["user_id"],
        email=doc.get("email"),
        name=doc.get("name"),
        is_guest=bool(doc.get("is_guest", False)),
        vulnerability_category=doc.get("vulnerability_category", VULNERABILITY_GENERAL),
        onboarding_completed=bool(doc.get("onboarding_completed", False)),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=AuthResponse,
    summary="Create a real account (email + password).",
)
async def register(
    body: RegisterRequest,
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
) -> AuthResponse:
    existing = await users_coll.find_one(
        {"email": body.email}, projection={"_id": 1}
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    now = _utc_now_naive()
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    doc: Dict[str, Any] = {
        "user_id": user_id,
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "name": body.name,
        "is_guest": False,
        "vulnerability_category": VULNERABILITY_GENERAL,
        "vulnerability_score": 0.0,
        "vulnerability_factors": [],
        "onboarding_completed": False,
        "created_at": now,
        "profile_last_updated": None,
    }
    await users_coll.insert_one(doc)
    logger.info("Registered new user user_id=%s email=%s", user_id, body.email)

    token = create_access_token(sub=user_id, is_guest=False)
    return AuthResponse(access_token=token, user=_user_to_out(doc))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate an existing account.",
)
async def login(
    body: LoginRequest,
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
) -> AuthResponse:
    user = await users_coll.find_one({"email": body.email})
    if user is None or not verify_password(
        body.password, user.get("hashed_password", "")
    ):
        # Same message either way to avoid email-enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(
        sub=user["user_id"],
        is_guest=bool(user.get("is_guest", False)),
    )
    logger.info("Login user_id=%s", user["user_id"])
    return AuthResponse(access_token=token, user=_user_to_out(user))


@router.post(
    "/guest",
    response_model=AuthResponse,
    summary="Create an anonymous guest session (no credentials needed).",
)
async def guest(
    body: GuestRequest,
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
) -> AuthResponse:
    now = _utc_now_naive()
    user_id = f"guest_{uuid.uuid4().hex[:16]}"
    doc: Dict[str, Any] = {
        "user_id": user_id,
        "is_guest": True,
        "device_id": body.device_id,
        "name": None,
        "vulnerability_category": VULNERABILITY_GENERAL,
        "vulnerability_score": 0.0,
        "vulnerability_factors": [],
        # Guests skip onboarding — they're flagged as "complete" by default
        # so endpoints relying on the flag don't block them. They can still
        # call /users/onboarding later to fill a profile.
        "onboarding_completed": True,
        "created_at": now,
        "profile_last_updated": now,
    }
    await users_coll.insert_one(doc)
    logger.info("Created guest user_id=%s device_id=%s", user_id, body.device_id)

    token = create_access_token(sub=user_id, is_guest=True)
    return AuthResponse(access_token=token, user=_user_to_out(doc))
