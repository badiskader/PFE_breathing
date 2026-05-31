"""
Notifications router.

Six endpoints:

  POST   /devices/register-push-token
  DELETE /devices/push-token
  GET    /notifications
  PATCH  /notifications/{notification_id}/read
  GET    /notifications/settings
  PATCH  /notifications/settings

Authentication note:
  `user_id` is currently passed as a query / body field. When JWT lands
  (Step 11), the dependency `get_current_user_id` will replace these.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import (
    get_current_user_id,
    get_device_tokens_collection,
    get_notifications_collection,
    get_users_collection,
)
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["notifications"])


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Default notification preferences (kept in sync with services.alert_dispatcher)
# ---------------------------------------------------------------------------

_DEFAULT_PREFERENCES: Dict[str, Any] = {
    "aqi_alerts_enabled": True,
    "forecast_alerts_enabled": True,
    "recommendation_alerts_enabled": True,
    "daily_summary_enabled": False,
    "language": None,
    "quiet_hours": {"enabled": False, "start": "22:00", "end": "07:00"},
}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RegisterPushTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expo_push_token: str = Field(..., min_length=1)
    platform: str = Field(..., min_length=1)  # "ios" / "android" / "web"
    device_id: Optional[str] = None
    app_version: Optional[str] = None


class DeletePushTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expo_push_token: str = Field(..., min_length=1)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    notification_id: str
    type: str
    title: str
    body: str
    severity: str
    sensor_id: Optional[str] = None
    created_at: datetime
    read: bool
    data: Dict[str, Any] = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    count: int
    unread_count: int
    notifications: List[NotificationResponse]


class QuietHours(BaseModel):
    enabled: bool = False
    start: str = "22:00"
    end: str = "07:00"


class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    aqi_alerts_enabled: bool = True
    forecast_alerts_enabled: bool = True
    recommendation_alerts_enabled: bool = True
    daily_summary_enabled: bool = False
    language: Optional[str] = None
    quiet_hours: QuietHours = Field(default_factory=QuietHours)


class NotificationSettingsUpdate(BaseModel):
    """Partial update — every field optional."""
    model_config = ConfigDict(extra="forbid")

    aqi_alerts_enabled: Optional[bool] = None
    forecast_alerts_enabled: Optional[bool] = None
    recommendation_alerts_enabled: Optional[bool] = None
    daily_summary_enabled: Optional[bool] = None
    language: Optional[str] = None
    quiet_hours: Optional[QuietHours] = None


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@router.post(
    "/devices/register-push-token",
    summary="Register an Expo push token for the current user",
)
async def register_push_token(
    body: RegisterPushTokenRequest,
    user_id: str = Depends(get_current_user_id),
    tokens_coll: AsyncIOMotorCollection = Depends(get_device_tokens_collection),
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
):
    # Confirm the user exists — refuse to register an orphan token.
    user = await users_coll.find_one(
        {"user_id": user_id}, projection={"_id": 1}
    )
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    now = _utc_now_naive()
    await tokens_coll.update_one(
        {"expo_push_token": body.expo_push_token},
        {
            "$set": {
                "user_id": user_id,
                "expo_push_token": body.expo_push_token,
                "platform": body.platform,
                "device_id": body.device_id,
                "app_version": body.app_version,
                "active": True,
                "updated_at": now,
            },
            "$setOnInsert": {"registered_at": now},
        },
        upsert=True,
    )
    logger.info(
        "Push token registered user=%s platform=%s",
        user_id, body.platform,
    )
    return {"success": True}


@router.delete(
    "/devices/push-token",
    summary="Unregister an Expo push token (e.g. on logout)",
)
async def delete_push_token(
    body: DeletePushTokenRequest,
    user_id: str = Depends(get_current_user_id),
    tokens_coll: AsyncIOMotorCollection = Depends(get_device_tokens_collection),
):
    result = await tokens_coll.update_one(
        {"expo_push_token": body.expo_push_token, "user_id": user_id},
        {"$set": {"active": False, "deactivated_at": _utc_now_naive()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Token not found for this user")
    return {"success": True}


# ---------------------------------------------------------------------------
# Notifications list / mark-read
# ---------------------------------------------------------------------------

@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="List a user's notifications, most recent first",
)
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    only_unread: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    notifications_coll: AsyncIOMotorCollection = Depends(get_notifications_collection),
) -> NotificationListResponse:
    query: Dict[str, Any] = {"user_id": user_id}
    if only_unread:
        query["read"] = False

    cursor = notifications_coll.find(
        query, projection={"_id": 0}
    ).sort([("created_at", -1)]).limit(limit)
    docs = await cursor.to_list(length=limit)

    unread_count = await notifications_coll.count_documents(
        {"user_id": user_id, "read": False}
    )

    return NotificationListResponse(
        count=len(docs),
        unread_count=unread_count,
        notifications=[NotificationResponse(**d) for d in docs],
    )


@router.patch(
    "/notifications/{notification_id}/read",
    summary="Mark one notification as read",
)
async def mark_notification_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    notifications_coll: AsyncIOMotorCollection = Depends(get_notifications_collection),
):
    result = await notifications_coll.update_one(
        {"notification_id": notification_id, "user_id": user_id},
        {"$set": {"read": True, "read_at": _utc_now_naive()}},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Notification {notification_id} not found for user {user_id}",
        )
    return {"success": True}


# ---------------------------------------------------------------------------
# Notification settings (stored inline on user document)
# ---------------------------------------------------------------------------

def _hydrate_settings(stored: Optional[dict]) -> NotificationSettings:
    """Merge stored preferences over defaults, return a validated model."""
    merged = dict(_DEFAULT_PREFERENCES)
    if stored:
        merged.update({k: v for k, v in stored.items() if v is not None})
        if isinstance(stored.get("quiet_hours"), dict):
            merged["quiet_hours"] = {
                **_DEFAULT_PREFERENCES["quiet_hours"],
                **stored["quiet_hours"],
            }
    return NotificationSettings(**merged)


@router.get(
    "/notifications/settings",
    response_model=NotificationSettings,
    summary="Get a user's notification preferences",
)
async def get_notification_settings(
    user_id: str = Depends(get_current_user_id),
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
) -> NotificationSettings:
    user = await users_coll.find_one(
        {"user_id": user_id},
        projection={"_id": 0, "notification_preferences": 1},
    )
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return _hydrate_settings(user.get("notification_preferences"))


@router.patch(
    "/notifications/settings",
    response_model=NotificationSettings,
    summary="Update a user's notification preferences (partial update)",
)
async def update_notification_settings(
    body: NotificationSettingsUpdate,
    user_id: str = Depends(get_current_user_id),
    users_coll: AsyncIOMotorCollection = Depends(get_users_collection),
) -> NotificationSettings:
    user = await users_coll.find_one(
        {"user_id": user_id},
        projection={"_id": 0, "notification_preferences": 1},
    )
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    current = _hydrate_settings(user.get("notification_preferences"))
    patch = body.model_dump(exclude_unset=True)
    if "quiet_hours" in patch and patch["quiet_hours"] is not None:
        # Already validated by Pydantic, dump to plain dict for Mongo.
        patch["quiet_hours"] = patch["quiet_hours"]

    new_prefs = current.model_dump()
    for k, v in patch.items():
        if v is None:
            continue
        new_prefs[k] = v

    await users_coll.update_one(
        {"user_id": user_id},
        {"$set": {"notification_preferences": new_prefs}},
    )
    logger.info("Notification settings updated for user=%s", user_id)
    return NotificationSettings(**new_prefs)
