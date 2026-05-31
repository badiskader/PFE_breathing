"""
Tools exposed to the Agno agents.

Each function is an async tool that Agno may call automatically. The LLM
selects tools based on:
  - the function name,
  - its docstring (READ THIS — Agno surfaces it to the LLM as the tool description),
  - its type hints.

Tools must return JSON-serializable data. They are stateless — every piece
of context (user_id, sensor_id) flows through arguments. The orchestrator
pre-resolves the user's sensor_id and injects it into each agent's
`additional_context`, so the LLM knows which values to pass.
"""

from datetime import datetime
from typing import List, Optional

from chatbot.retriever import retrieve_relevant_chunks
from chatbot.session_manager import get_recent_history
from core.logger import get_logger
from core.mongo_client import aqi_results, predictions, users

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers (not tools)
# ---------------------------------------------------------------------------

_SEASONS = {
    "winter": (12, 1, 2),
    "spring": (3, 4, 5),
    "summer": (6, 7, 8),
    "fall":   (9, 10, 11),
    "autumn": (9, 10, 11),
}


def _isoize(value):
    """Convert datetime to ISO string for JSON-safe tool returns."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------

async def get_current_air_quality(sensor_id: str) -> dict:
    """Return the latest measured AQI for a given sensor.

    Use this to ground answers in the user's actual current local conditions.

    Args:
        sensor_id: Sensor identifier (e.g. 'AQ_CST_01'). Use the value
            provided in the SESSION CONTEXT block.

    Returns:
        Dict with sensor_id, timestamp, aqi_score, aqi_category, risk_level,
        dominant_pollutant, sub_indices. Or {"error": "..."} if no data.
    """
    doc = await aqi_results().find_one(
        {"sensor_id": sensor_id},
        sort=[("timestamp", -1)],
        projection={"_id": 0},
    )
    if not doc:
        return {"error": f"No AQI measurement available for sensor {sensor_id}"}
    doc["timestamp"] = _isoize(doc.get("timestamp"))
    logger.info(
        "tool:get_current_air_quality sensor_id=%s aqi=%s category=%s",
        sensor_id, doc.get("aqi_score"), doc.get("aqi_category"),
    )
    return doc


async def get_user_profile(user_id: str) -> dict:
    """Return a user's health profile and derived vulnerability category.

    Use this when generating personalized advice — read the conditions
    (asthma, cardiovascular, allergies, chronic_diseases, smoking_status,
    activity_level, pollution_sensitivity, age, etc.) and reference them
    explicitly in your reply.

    Args:
        user_id: User identifier. Use the value from SESSION CONTEXT.

    Returns:
        Dict with `profile`, `vulnerability_category`, `vulnerability_score`,
        `vulnerability_factors`. Or {"error": "..."} if user not onboarded.
    """
    user = await users().find_one(
        {"user_id": user_id},
        projection={
            "_id": 0,
            "profile": 1,
            "vulnerability_category": 1,
            "vulnerability_score": 1,
            "vulnerability_factors": 1,
        },
    )
    if not user:
        return {
            "error": (
                f"User {user_id} not found. Ask them to complete onboarding "
                f"via POST /users/onboarding before personalized advice."
            )
        }
    logger.info(
        "tool:get_user_profile user_id=%s category=%s",
        user_id, user.get("vulnerability_category"),
    )
    return user


async def get_conversation_history(session_id: str, last_n: int = 20) -> list:
    """Return the last N messages of the current chat session.

    Use this when the user references earlier turns (e.g. "as I said before"
    or "what was that recommendation again?"). The most recent N messages
    are already in the SESSION CONTEXT block — call this only to look
    further back.

    Args:
        session_id: Session identifier. Use the value from SESSION CONTEXT.
        last_n: Number of most-recent messages to return.

    Returns:
        List of {role, content, agent_used, timestamp} dicts, oldest first.
    """
    msgs = await get_recent_history(session_id, last_n)
    result = [
        {
            "role": m.role,
            "content": m.content,
            "agent_used": m.agent_used,
            "timestamp": _isoize(m.timestamp),
        }
        for m in msgs
    ]
    logger.info("tool:get_conversation_history session_id=%s n=%d", session_id, len(result))
    return result


async def query_knowledge_base(query: str, top_k: int = 5) -> list:
    """Search the air-quality knowledge base for chunks relevant to a query.

    Use this for general science questions (definitions, mechanisms,
    WHO/EPA guidelines, health effects). ALWAYS call this BEFORE answering
    a general question, and ground your answer in the returned chunks.

    Args:
        query: Natural-language query.
        top_k: How many chunks to return. Default 5.

    Returns:
        List of {chunk_id, source, content, score} dicts.
    """
    chunks = await retrieve_relevant_chunks(query, top_k=top_k)
    result = [
        {
            "chunk_id": c.chunk_id,
            "source": c.source,
            "content": c.content,
            "score": round(c.score, 3),
        }
        for c in chunks
    ]
    logger.info(
        "tool:query_knowledge_base query=%r retrieved=%d top_score=%.3f",
        query[:80], len(result), result[0]["score"] if result else 0.0,
    )
    return result


async def get_forecast(
    sensor_id: str,
    target_datetime: Optional[str] = None,
) -> dict:
    """Return the 12-hour pollution forecast for a sensor.

    The forecast is generated every simulated hour by the upstream scheduler
    and is stored in MongoDB. If no forecast is available yet, returns
    {"available": false, ...}. In that case, the caller MUST fall back to
    `get_historical_data` for the same sensor + the relevant hour-of-day.

    Args:
        sensor_id: Sensor identifier. Use the SESSION CONTEXT value.
        target_datetime: Optional ISO-8601 datetime. If provided, the tool
            returns just the forecast hour closest to that datetime;
            otherwise all 12 hours are returned.

    Returns:
        {"available": true, "sensor_id", "generated_at", "horizon_hours",
         "predictions": [12 hourly entries]}
        OR
        {"available": false, "reason": str, "fallback_hint": str}.
    """
    doc = await predictions().find_one({"sensor_id": sensor_id}, projection={"_id": 0})
    if not doc or not doc.get("predictions"):
        logger.info("tool:get_forecast sensor_id=%s available=False", sensor_id)
        return {
            "available": False,
            "sensor_id": sensor_id,
            "reason": "No forecast generated yet for this sensor.",
            "fallback_hint": (
                "Call get_historical_data with this sensor_id and the "
                "user's intended hour_of_day to provide a typical pattern."
            ),
        }

    preds = doc["predictions"]
    for h in preds:
        h["timestamp"] = _isoize(h.get("timestamp"))

    # If a target datetime was supplied, return just the closest hour.
    if target_datetime:
        try:
            target = datetime.fromisoformat(target_datetime.replace("Z", "+00:00"))
            best, best_dt = None, None
            for h in preds:
                try:
                    ht = datetime.fromisoformat(h["timestamp"])
                except Exception:
                    continue
                if (best is None) or abs((ht - target).total_seconds()) < abs((best_dt - target).total_seconds()):
                    best, best_dt = h, ht
            if best:
                return {
                    "available": True,
                    "sensor_id": doc["sensor_id"],
                    "matched_hour": best,
                    "generated_at": _isoize(doc.get("generated_at")),
                }
            return {
                "available": False,
                "sensor_id": sensor_id,
                "reason": "Forecast doesn't cover that datetime.",
                "fallback_hint": (
                    f"Call get_historical_data with hour_of_day={target.hour} "
                    f"and day_of_week={target.weekday()}."
                ),
            }
        except Exception as e:
            return {"error": f"Invalid target_datetime: {e}", "available": False}

    logger.info(
        "tool:get_forecast sensor_id=%s available=True hours=%d",
        sensor_id, len(preds),
    )
    return {
        "available": True,
        "sensor_id": doc["sensor_id"],
        "generated_at": _isoize(doc.get("generated_at")),
        "horizon_hours": doc.get("forecast_horizon_hours", len(preds)),
        "predictions": preds,
    }


async def get_historical_data(
    sensor_id: str,
    start_hour: Optional[int] = None,
    end_hour: Optional[int] = None,
    day_of_week: Optional[int] = None,
    season: Optional[str] = None,
) -> dict:
    """Return historical AQI statistics for a sensor, optionally filtered
    by hour-of-day window, day-of-week, and/or season.

    This is the FALLBACK to use when `get_forecast` returns
    available=false. By passing the hour-of-day the user is asking about
    (e.g. "this afternoon" → start_hour=14, end_hour=18), you can give a
    historical pattern in place of a missing forecast.

    Args:
        sensor_id: Sensor identifier.
        start_hour: Lower bound (inclusive) of the hour-of-day filter (0–23).
        end_hour:   Upper bound (inclusive) of the hour-of-day filter (0–23).
        day_of_week: 0=Monday .. 6=Sunday. Omit for all days.
        season: One of "winter", "spring", "summer", "fall"/"autumn".

    Returns:
        {"n_samples", "avg_aqi", "min_aqi", "max_aqi", "p25_aqi", "p75_aqi",
         "filters": {...}} or {"error": ..., "filters": ...} if no samples.
    """
    pipeline: List[dict] = [{"$match": {"sensor_id": sensor_id}}]

    needs_addfields = any(v is not None for v in
                          (start_hour, end_hour, day_of_week, season))
    if needs_addfields:
        pipeline.append({"$addFields": {
            "hour": {"$hour": "$timestamp"},
            "month": {"$month": "$timestamp"},
            "dow0": {"$subtract": [{"$isoDayOfWeek": "$timestamp"}, 1]},  # 0=Mon..6=Sun
        }})

    if start_hour is not None and end_hour is not None:
        if start_hour <= end_hour:
            pipeline.append({"$match": {"hour": {"$gte": int(start_hour), "$lte": int(end_hour)}}})
        else:
            # Wrap-around window (e.g. 22..3 → night).
            pipeline.append({"$match": {"$or": [
                {"hour": {"$gte": int(start_hour)}},
                {"hour": {"$lte": int(end_hour)}},
            ]}})
    elif start_hour is not None:
        pipeline.append({"$match": {"hour": int(start_hour)}})

    if day_of_week is not None:
        pipeline.append({"$match": {"dow0": int(day_of_week)}})

    if season:
        months = _SEASONS.get(season.lower())
        if months:
            pipeline.append({"$match": {"month": {"$in": list(months)}}})

    pipeline.append({"$group": {
        "_id": None,
        "n": {"$sum": 1},
        "avg_aqi": {"$avg": "$aqi_score"},
        "min_aqi": {"$min": "$aqi_score"},
        "max_aqi": {"$max": "$aqi_score"},
        "aqis": {"$push": "$aqi_score"},
    }})

    docs = await aqi_results().aggregate(pipeline).to_list(length=1)
    filters = {
        "sensor_id": sensor_id,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "day_of_week": day_of_week,
        "season": season,
    }
    if not docs or docs[0]["n"] == 0:
        logger.info("tool:get_historical_data sensor_id=%s filters=%s n=0", sensor_id, filters)
        return {"error": "No historical samples match the filter.", "filters": filters}

    r = docs[0]
    aqis = sorted(r["aqis"])
    n = r["n"]
    p25 = aqis[int(n * 0.25)] if n > 0 else None
    p75 = aqis[int(n * 0.75)] if n > 0 else None

    result = {
        "filters": filters,
        "n_samples": n,
        "avg_aqi": round(r["avg_aqi"], 1),
        "min_aqi": r["min_aqi"],
        "max_aqi": r["max_aqi"],
        "p25_aqi": p25,
        "p75_aqi": p75,
    }
    logger.info(
        "tool:get_historical_data sensor_id=%s filters=%s n=%d avg=%.1f",
        sensor_id, filters, n, r["avg_aqi"],
    )
    return result


async def compute_statistics(values: list) -> dict:
    """Compute basic statistics for a list of numbers.

    Args:
        values: List of numeric values.

    Returns:
        {"n", "mean", "min", "max", "stdev", "p25", "p50", "p75"} or error.
    """
    if not values:
        return {"error": "empty list of values"}
    try:
        import statistics as _stats
        sorted_v = sorted(float(v) for v in values)
        n = len(sorted_v)
        return {
            "n": n,
            "mean": round(_stats.mean(sorted_v), 2),
            "min": sorted_v[0],
            "max": sorted_v[-1],
            "stdev": round(_stats.stdev(sorted_v), 2) if n > 1 else 0.0,
            "p25": sorted_v[int(n * 0.25)],
            "p50": sorted_v[int(n * 0.50)],
            "p75": sorted_v[min(n - 1, int(n * 0.75))],
        }
    except (ValueError, TypeError) as e:
        return {"error": f"Could not parse values: {e}"}
