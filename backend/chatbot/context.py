"""
Orchestrator-internal helpers — NOT exposed as Agno tools.

These functions resolve per-session context that the orchestrator
pre-computes (user → nearest sensor, current AQI snapshot, conversation
history block) before handing the message to the Agno team.
"""

import math
from typing import List, Optional

from chatbot.session_manager import ChatMessage
from core.logger import get_logger
from core.mongo_client import aqi_results, predictions, sensor_readings, users

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Sensor resolution
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def resolve_user_sensor(user_id: str) -> Optional[str]:
    """Return the sensor_id closest to the user's primary preferred location.

    Fallback order:
      1. Nearest sensor to `users.profile.preferred_locations[0]`
      2. First sensor that has predictions
      3. None (the orchestrator will pass UNKNOWN to the team)
    """
    user = await users().find_one(
        {"user_id": user_id}, projection={"profile.preferred_locations": 1}
    )
    if user:
        locs = ((user.get("profile") or {}).get("preferred_locations") or [])
        if locs:
            lat = locs[0]["latitude"]
            lon = locs[0]["longitude"]

            # Build a one-row-per-sensor list of latest coordinates.
            sensors = await sensor_readings().aggregate([
                {"$sort": {"sensor_id": 1, "timestamp": -1}},
                {"$group": {
                    "_id": "$sensor_id",
                    "lat": {"$first": "$latitude"},
                    "lon": {"$first": "$longitude"},
                }},
            ]).to_list(length=None)

            if sensors:
                best_id, best_dist = None, float("inf")
                for s in sensors:
                    d = _haversine_km(lat, lon, s["lat"], s["lon"])
                    if d < best_dist:
                        best_dist, best_id = d, s["_id"]
                return best_id

    # Fallback 1: any sensor that has a forecast.
    ids = await predictions().distinct("sensor_id")
    if ids:
        return sorted(ids)[0]

    # Fallback 2: any sensor that has at least one AQI reading.
    ids = await aqi_results().distinct("sensor_id")
    if ids:
        return sorted(ids)[0]

    # Fallback 3: any sensor that ever wrote a raw reading.
    ids = await sensor_readings().distinct("sensor_id")
    return sorted(ids)[0] if ids else None


# ---------------------------------------------------------------------------
# History formatting
# ---------------------------------------------------------------------------

def format_history_for_context(history: List[ChatMessage], max_chars: int = 250) -> str:
    """Render the last N chat turns as a plain-text block for injection
    into Agno's `additional_context`."""
    if not history:
        return ""
    lines = ["RECENT CONVERSATION (oldest → most recent):"]
    for m in history:
        role = "User" if m.role == "user" else "Assistant"
        snippet = m.content[:max_chars]
        if m.agent_used and m.role == "assistant":
            lines.append(f"  {role} [{m.agent_used}]: {snippet}")
        else:
            lines.append(f"  {role}: {snippet}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Current AQI snapshot (pre-fetched once per turn)
# ---------------------------------------------------------------------------

def format_aqi_snapshot(current_aqi: dict) -> str:
    """Render the pre-fetched AQI as a context block.
    Empty string if AQI is missing or errored."""
    if not current_aqi or current_aqi.get("error"):
        return ""
    lines = [
        "CURRENT AQI SNAPSHOT (pre-fetched — DO NOT call "
        "get_current_air_quality again unless you need fresh data):",
        f"  sensor_id          = {current_aqi.get('sensor_id')}",
        f"  aqi_score          = {current_aqi.get('aqi_score')}",
        f"  aqi_category       = {current_aqi.get('aqi_category')}",
        f"  risk_level         = {current_aqi.get('risk_level')}",
        f"  dominant_pollutant = {current_aqi.get('dominant_pollutant')}",
        f"  timestamp          = {current_aqi.get('timestamp')}",
    ]
    return "\n".join(lines)
