"""
Expo Push API wrapper.

Single chokepoint for sending push notifications to Expo push tokens.
Provider can be swapped by changing `EXPO_PUSH_URL` (e.g. self-hosted
Expo, mock for tests).

Expo Push API: https://docs.expo.dev/push-notifications/sending-notifications/
"""

from typing import Any, Dict, List, Optional

import httpx

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class PushError(Exception):
    """The Expo push service returned a non-OK response."""


class PushUnavailableError(PushError):
    """Push service is unreachable (network or DNS error)."""


async def send_push(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    priority: str = "high",
    sound: str = "default",
    channel_id: Optional[str] = None,
) -> dict:
    """Send a single notification to one or more Expo push tokens.

    Args:
        tokens:     One or more ExponentPushToken[...] strings.
        title:      Notification title.
        body:       Notification body.
        data:       Optional JSON payload for deep-link navigation
                    (e.g. {"screen": "MyAir", "sensor_id": "..."}).
        priority:   "default" or "high".
        sound:      "default" or null.
        channel_id: Android notification channel id (optional).

    Returns:
        Expo response dict (one "data" entry per token with a ticket id).

    Raises:
        PushUnavailableError: network failure.
        PushError:            non-200 response.
    """
    if not tokens:
        return {"sent": 0, "tickets": []}

    messages = []
    for token in tokens:
        msg = {
            "to": token,
            "title": title,
            "body": body,
            "data": data or {},
            "priority": priority,
            "sound": sound,
        }
        if channel_id:
            msg["channelId"] = channel_id
        messages.append(msg)

    url = settings.EXPO_PUSH_URL
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=settings.EXPO_PUSH_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post(url, json=messages, headers=headers)
        except httpx.RequestError as e:
            raise PushUnavailableError(
                f"Expo push request failed (url={url}): {e}"
            ) from e

    if resp.status_code != 200:
        raise PushError(
            f"Expo push HTTP {resp.status_code} (url={url}): {resp.text[:500]}"
        )

    try:
        result = resp.json()
    except ValueError as e:
        raise PushError(f"Expo push returned non-JSON body: {e}") from e

    logger.info(
        "Expo push sent | tokens=%d response_keys=%s",
        len(tokens),
        list(result.keys()) if isinstance(result, dict) else type(result).__name__,
    )
    return result
