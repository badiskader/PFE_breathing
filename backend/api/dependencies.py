"""
FastAPI dependency-injection helpers.

Two concerns live here:

  1. Collection accessors as DI dependencies — routers stay clean and
     never import Motor handles directly.
  2. Auth chokepoint (`get_current_user_id`) — decodes the JWT from the
     `Authorization: Bearer <token>` header. Use the `_optional` variant
     on routes where anonymous access is allowed.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorCollection

from services.auth_service import InvalidTokenError, decode_access_token

from core.mongo_client import (
    aqi_results as _aqi_results,
    chat_sessions as _chat_sessions,
    dashboard_recommendations as _dashboard_recommendations,
    device_tokens as _device_tokens,
    knowledge_chunks as _knowledge_chunks,
    notifications as _notifications,
    predictions as _predictions,
    sensor_readings as _sensor_readings,
    users as _users,
)


# ---------------------------------------------------------------------------
# Collection accessors (used via Depends in routers)
# ---------------------------------------------------------------------------

def get_users_collection() -> AsyncIOMotorCollection:
    return _users()


def get_sensor_readings_collection() -> AsyncIOMotorCollection:
    return _sensor_readings()


def get_aqi_collection() -> AsyncIOMotorCollection:
    return _aqi_results()


def get_predictions_collection() -> AsyncIOMotorCollection:
    return _predictions()


def get_dashboard_recommendations_collection() -> AsyncIOMotorCollection:
    return _dashboard_recommendations()


def get_chat_sessions_collection() -> AsyncIOMotorCollection:
    return _chat_sessions()


def get_knowledge_chunks_collection() -> AsyncIOMotorCollection:
    return _knowledge_chunks()


def get_notifications_collection() -> AsyncIOMotorCollection:
    return _notifications()


def get_device_tokens_collection() -> AsyncIOMotorCollection:
    return _device_tokens()


# ---------------------------------------------------------------------------
# Auth — JWT bearer
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def _decode_or_401(cred: HTTPAuthorizationCredentials) -> dict:
    try:
        return decode_access_token(cred.credentials)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user_id(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """REQUIRED auth — return user_id from JWT or raise 401.

    Use on every endpoint that needs to know who the caller is.
    """
    if cred is None or not cred.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token. Call POST /auth/guest or /auth/login.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_or_401(cred)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return user_id


async def get_current_user_id_optional(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[str]:
    """OPTIONAL auth — return user_id from JWT if present, else None.

    Use on endpoints that work both anonymously and for known users.
    """
    if cred is None or not cred.credentials:
        return None
    try:
        payload = decode_access_token(cred.credentials)
    except InvalidTokenError:
        return None
    return payload.get("sub")


async def get_current_token_claims(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Full JWT claims (sub, is_guest, iat, exp). Required."""
    if cred is None or not cred.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_or_401(cred)
