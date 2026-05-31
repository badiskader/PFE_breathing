"""
Alert dispatch logic.

Called by `recommendation_scheduler` at the end of each cycle. Given the
list of (sensor_id, category, previous_doc, new_rule) transitions:

  1. Filters to "alertable" transitions:
       - new urgency ≥ ALERT_URGENCY_THRESHOLD
       - new urgency > previous urgency (i.e. an escalation)
  2. For each affected vulnerability category, loads users in that category
     ONCE and the sensor coordinate table ONCE.
  3. For each user whose nearest sensor matches the alerted sensor:
       - check opted in (notification_preferences.recommendation_alerts_enabled)
       - check quiet hours (skipped for danger-level alerts)
       - check cooldown (last notification for this (user, sensor) pair)
       - record notification document
       - push via Expo if user has registered tokens

Persistence happens BEFORE the push so the in-app notification center
shows the alert even if push delivery fails or the user has no device
tokens registered (useful for the thesis demo without a real phone).
"""

import math
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.config import settings
from core.logger import get_logger
from core.mongo_client import (
    device_tokens,
    notifications,
    sensor_readings,
    users,
)
from services.push_client import PushError, PushUnavailableError, send_push
from services.recommendation_engine import (
    URGENCY_AVOID,
    URGENCY_CAUTION,
    URGENCY_DANGER,
    URGENCY_SAFE,
    RuleRecommendationResult,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

URGENCY_RANK: Dict[str, int] = {
    URGENCY_SAFE: 0,
    URGENCY_CAUTION: 1,
    URGENCY_AVOID: 2,
    URGENCY_DANGER: 3,
}

NOTIFICATION_TYPE_RECO = "recommendation_alert"

_DEFAULT_PREFERENCES = {
    "aqi_alerts_enabled": True,
    "forecast_alerts_enabled": True,
    "recommendation_alerts_enabled": True,
    "daily_summary_enabled": False,
    "language": None,  # falls back to settings.ALERT_DEFAULT_LANGUAGE
    "quiet_hours": {"enabled": False, "start": "22:00", "end": "07:00"},
}

# Localized notification templates. Severity = urgency_level.
_TEMPLATES: Dict[str, Dict[str, Dict[str, str]]] = {
    "fr": {
        URGENCY_AVOID: {
            "title": "⚠️ Qualité de l'air dégradée",
            "body": (
                "L'air autour de {sensor_id} est préoccupant ({category}). "
                "Polluants à surveiller : {pollutants}. "
                "Limitez vos activités extérieures."
            ),
        },
        URGENCY_DANGER: {
            "title": "🚨 Pollution dangereuse",
            "body": (
                "L'air autour de {sensor_id} est dangereux ({category}). "
                "Polluants critiques : {pollutants}. "
                "Restez à l'intérieur et évitez tout effort."
            ),
        },
    },
    "en": {
        URGENCY_AVOID: {
            "title": "⚠️ Air quality is degraded",
            "body": (
                "Air near {sensor_id} is unhealthy ({category}). "
                "Pollutants of concern: {pollutants}. "
                "Limit outdoor activities."
            ),
        },
        URGENCY_DANGER: {
            "title": "🚨 Hazardous pollution",
            "body": (
                "Air near {sensor_id} is hazardous ({category}). "
                "Critical pollutants: {pollutants}. "
                "Stay indoors and avoid exertion."
            ),
        },
    },
}


# ---------------------------------------------------------------------------
# Sensor coordinate cache (refreshed per cycle by the dispatcher)
# ---------------------------------------------------------------------------

async def _load_sensor_coordinates() -> Dict[str, Tuple[float, float]]:
    """Return {sensor_id: (lat, lon)} from the latest sensor_readings docs."""
    pipeline = [
        {"$sort": {"sensor_id": 1, "timestamp": -1}},
        {"$group": {
            "_id": "$sensor_id",
            "lat": {"$first": "$latitude"},
            "lon": {"$first": "$longitude"},
        }},
    ]
    docs = await sensor_readings().aggregate(pipeline).to_list(length=None)
    return {d["_id"]: (d["lat"], d["lon"]) for d in docs}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_sensor_for_user(
    user: dict,
    sensor_coords: Dict[str, Tuple[float, float]],
) -> Optional[str]:
    """Pick the sensor closest to the user's first preferred location."""
    locs = ((user.get("profile") or {}).get("preferred_locations") or [])
    if not locs:
        return None
    lat, lon = locs[0]["latitude"], locs[0]["longitude"]
    best_id, best_dist = None, float("inf")
    for sid, (slat, slon) in sensor_coords.items():
        d = _haversine_km(lat, lon, slat, slon)
        if d < best_dist:
            best_dist, best_id = d, sid
    return best_id


# ---------------------------------------------------------------------------
# Alertability + per-user gates
# ---------------------------------------------------------------------------

def _is_alertable(
    previous_doc: Optional[dict],
    new_rule: RuleRecommendationResult,
) -> bool:
    """True if the new rule output crosses the alert threshold AND
    represents an escalation vs the previous output."""
    threshold_rank = URGENCY_RANK.get(settings.ALERT_URGENCY_THRESHOLD, 2)
    new_rank = URGENCY_RANK.get(new_rule.urgency_level, 0)

    if new_rank < threshold_rank:
        return False

    if previous_doc is None:
        # First time we evaluate this combo AND we're at/above threshold.
        return True

    prev_urgency = (previous_doc.get("rule_output") or {}).get("urgency_level")
    prev_rank = URGENCY_RANK.get(prev_urgency, 0)
    return new_rank > prev_rank


def _merge_preferences(user_prefs: Optional[dict]) -> dict:
    """Merge stored prefs over the default template (missing keys default)."""
    merged = dict(_DEFAULT_PREFERENCES)
    if user_prefs:
        merged.update({k: v for k, v in user_prefs.items() if v is not None})
        if "quiet_hours" in user_prefs:
            merged["quiet_hours"] = {
                **_DEFAULT_PREFERENCES["quiet_hours"],
                **(user_prefs.get("quiet_hours") or {}),
            }
    return merged


def _parse_hhmm(s: str) -> Tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def _in_quiet_hours(prefs: dict, now: datetime) -> bool:
    qh = prefs.get("quiet_hours") or {}
    if not qh.get("enabled"):
        return False
    try:
        start = _parse_hhmm(qh.get("start", "22:00"))
        end = _parse_hhmm(qh.get("end", "07:00"))
    except (ValueError, AttributeError):
        return False
    now_hm = (now.hour, now.minute)
    if start <= end:
        return start <= now_hm <= end
    # Wraps midnight (e.g. 22:00 → 07:00).
    return now_hm >= start or now_hm <= end


async def _cooldown_elapsed(user_id: str, sensor_id: str, now: datetime) -> bool:
    """True if no notification for (user, sensor) within ALERT_COOLDOWN_HOURS."""
    last = await notifications().find_one(
        {"user_id": user_id, "sensor_id": sensor_id},
        sort=[("created_at", -1)],
        projection={"created_at": 1},
    )
    if not last:
        return True
    last_at = last.get("created_at")
    if not isinstance(last_at, datetime):
        return True
    elapsed_hours = (now - last_at).total_seconds() / 3600.0
    return elapsed_hours >= settings.ALERT_COOLDOWN_HOURS


# ---------------------------------------------------------------------------
# Notification content + persistence + push
# ---------------------------------------------------------------------------

def _build_notification_text(
    rule: RuleRecommendationResult,
    sensor_id: str,
    language: str,
) -> Tuple[str, str]:
    lang = language if language in _TEMPLATES else settings.ALERT_DEFAULT_LANGUAGE
    if lang not in _TEMPLATES:
        lang = "fr"
    tpl = _TEMPLATES[lang].get(rule.urgency_level)
    if not tpl:
        # Shouldn't happen — _is_alertable filters out non-alert urgencies.
        tpl = _TEMPLATES[lang][URGENCY_AVOID]

    pollutants = ", ".join(rule.flagged_pollutants) or "PM2.5"
    title = tpl["title"]
    body = tpl["body"].format(
        sensor_id=sensor_id,
        category=rule.forecast_category,
        pollutants=pollutants,
    )
    return title, body


async def _record_notification(
    *,
    user_id: str,
    sensor_id: str,
    title: str,
    body: str,
    severity: str,
    rule: RuleRecommendationResult,
    now: datetime,
) -> str:
    notification_id = f"notif_{uuid.uuid4().hex[:16]}"
    doc = {
        "notification_id": notification_id,
        "user_id": user_id,
        "type": NOTIFICATION_TYPE_RECO,
        "title": title,
        "body": body,
        "severity": severity,
        "sensor_id": sensor_id,
        "created_at": now,
        "read": False,
        "data": {
            "screen": "MyAir",
            "sensor_id": sensor_id,
            "forecast_category": rule.forecast_category,
            "urgency_level": severity,
            "flagged_pollutants": rule.flagged_pollutants,
        },
    }
    await notifications().insert_one(doc)
    return notification_id


async def _get_user_active_tokens(user_id: str) -> List[str]:
    cursor = device_tokens().find(
        {"user_id": user_id, "active": {"$ne": False}},
        projection={"expo_push_token": 1, "_id": 0},
    )
    docs = await cursor.to_list(length=20)
    return [d["expo_push_token"] for d in docs if d.get("expo_push_token")]


# ---------------------------------------------------------------------------
# Per-user dispatch
# ---------------------------------------------------------------------------

async def _try_send_user_alert(
    user: dict,
    sensor_id: str,
    rule: RuleRecommendationResult,
    now: datetime,
) -> bool:
    """Run all gates, then record + push. Returns True if a notification was recorded."""
    user_id = user["user_id"]
    prefs = _merge_preferences(user.get("notification_preferences"))

    if not prefs.get("recommendation_alerts_enabled", True):
        return False

    if (rule.urgency_level != URGENCY_DANGER
            and _in_quiet_hours(prefs, now)):
        return False

    if not await _cooldown_elapsed(user_id, sensor_id, now):
        return False

    language = prefs.get("language") or settings.ALERT_DEFAULT_LANGUAGE
    title, body = _build_notification_text(rule, sensor_id, language)

    notification_id = await _record_notification(
        user_id=user_id,
        sensor_id=sensor_id,
        title=title,
        body=body,
        severity=rule.urgency_level,
        rule=rule,
        now=now,
    )

    tokens = await _get_user_active_tokens(user_id)
    if tokens:
        try:
            await send_push(
                tokens,
                title=title,
                body=body,
                data={
                    "screen": "MyAir",
                    "sensor_id": sensor_id,
                    "notification_id": notification_id,
                },
            )
        except (PushError, PushUnavailableError) as e:
            logger.warning(
                "Expo push failed user=%s sensor=%s: %s",
                user_id, sensor_id, e,
            )

    logger.info(
        "Alert dispatched | user=%s sensor=%s urgency=%s notif_id=%s tokens=%d",
        user_id, sensor_id, rule.urgency_level, notification_id, len(tokens),
    )
    return True


# ---------------------------------------------------------------------------
# Public entry — called by the recommendation scheduler
# ---------------------------------------------------------------------------

async def dispatch_alerts_for_cycle(
    transitions: List[Tuple[str, str, Optional[dict], RuleRecommendationResult]],
    now: datetime,
) -> Dict[str, int]:
    """Process a batch of (sensor_id, category, previous_doc, new_rule).

    For each alertable transition, find affected users and try to notify them.
    The function is best-effort: per-user failures are logged and do not
    abort the cycle.

    Returns:
        metrics: {alertable, considered_users, users_notified, errors}
    """
    metrics = {
        "alertable": 0,
        "considered_users": 0,
        "users_notified": 0,
        "errors": 0,
    }

    # 1. Keep only alertable transitions.
    alertable = [
        (s, c, prev, new) for (s, c, prev, new) in transitions
        if _is_alertable(prev, new)
    ]
    metrics["alertable"] = len(alertable)
    if not alertable:
        return metrics

    # 2. Group by category for one user-lookup per category.
    by_category: Dict[str, List[Tuple[str, RuleRecommendationResult]]] = {}
    for sensor_id, category, _prev, new_rule in alertable:
        by_category.setdefault(category, []).append((sensor_id, new_rule))

    # 3. Load sensor coordinates ONCE for nearest-sensor matching.
    sensor_coords = await _load_sensor_coordinates()
    if not sensor_coords:
        logger.warning(
            "Alert dispatcher: no sensor coordinates available — skipping all alerts"
        )
        return metrics

    # 4. Per category, load users ONCE and check each.
    for category, sensor_transitions in by_category.items():
        cursor = users().find(
            {"vulnerability_category": category},
            projection={
                "user_id": 1,
                "profile.preferred_locations": 1,
                "notification_preferences": 1,
                "_id": 0,
            },
        )
        category_users = await cursor.to_list(length=None)
        metrics["considered_users"] += len(category_users)

        # Pre-compute each user's nearest sensor once.
        user_to_nearest = {
            u["user_id"]: _nearest_sensor_for_user(u, sensor_coords)
            for u in category_users
        }

        for sensor_id, new_rule in sensor_transitions:
            for user in category_users:
                if user_to_nearest.get(user["user_id"]) != sensor_id:
                    continue
                try:
                    sent = await _try_send_user_alert(
                        user, sensor_id, new_rule, now
                    )
                    if sent:
                        metrics["users_notified"] += 1
                except Exception as e:
                    metrics["errors"] += 1
                    logger.exception(
                        "Unexpected error dispatching to user=%s sensor=%s: %s",
                        user.get("user_id"), sensor_id, e,
                    )

    logger.info(
        "Alert cycle dispatched | alertable=%d users_considered=%d notified=%d errors=%d",
        metrics["alertable"], metrics["considered_users"],
        metrics["users_notified"], metrics["errors"],
    )
    return metrics
