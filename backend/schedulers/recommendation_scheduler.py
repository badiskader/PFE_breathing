"""
Type 1 (dashboard) recommendation scheduler.

For every (sensor_id × vulnerability_category) combination:
  1. Read the latest forecast from `predictions`.
  2. Run the deterministic rule engine (Layer A).
  3. Decide via `should_regenerate_recommendation` whether to call the LLM.
  4. If yes: call Groq (Layer B). If no: reuse previous text.
  5. Always overwrite rule_output (cheap, deterministic).
  6. Upsert into `dashboard_recommendations`.

The mobile dashboard endpoint will be a pure READ of this collection —
no LLM call at request time.

The scheduler is thin. All recommendation logic lives in
`services/recommendation_engine.py`.
"""

import asyncio
import signal
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from core.config import settings
from core.logger import get_logger
from core.mongo_client import (
    close_mongo_connection,
    connect_to_mongo,
    dashboard_recommendations,
    ensure_dashboard_recommendations_indexes,
    ensure_device_tokens_indexes,
    ensure_notifications_indexes,
    predictions,
)
from services.alert_dispatcher import dispatch_alerts_for_cycle
from services.recommendation_engine import (
    RecommendationError,
    RuleRecommendationResult,
    VULNERABILITY_CATEGORIES,
    compute_rule_based_recommendation,
    generate_recommendation_text,
    should_regenerate_recommendation,
)

logger = get_logger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

async def _discover_active_sensors() -> List[str]:
    """Sensors that currently have a forecast document."""
    return sorted(await predictions().distinct("sensor_id"))


# ---------------------------------------------------------------------------
# Per (sensor, category) processing
# ---------------------------------------------------------------------------

async def _process_combination(
    sensor_id: str,
    category: str,
    forecast_hours: List[dict],
    now: datetime,
) -> Tuple[UpdateOne, str, str, Optional[dict], RuleRecommendationResult]:
    """Build the upsert op for one (sensor, category) combination.

    Returns: (op, action, reason, previous_doc, rule) — the last two are
    handed to the alert dispatcher at the end of the cycle so it can
    detect urgency escalations.
    """
    rule: RuleRecommendationResult = compute_rule_based_recommendation(
        category, forecast_hours
    )

    previous = await dashboard_recommendations().find_one(
        {"sensor_id": sensor_id, "vulnerability_category": category}
    )

    regen, reason = should_regenerate_recommendation(
        previous,
        rule,
        regen_interval_hours=settings.RECOMMENDATION_REGEN_INTERVAL_HOURS,
        now=now,
    )

    if regen:
        text = await generate_recommendation_text(rule)
        action = "regenerated"
    else:
        # previous is guaranteed non-None here (otherwise regen would be True).
        text = previous["recommendation_text"]
        action = "reused"

    doc = {
        "sensor_id": sensor_id,
        "vulnerability_category": category,
        "generated_at": now,
        "forecast_aqi_max": rule.forecast_aqi_max,
        "forecast_category": rule.forecast_category,
        "rule_output": rule.model_dump(mode="python"),
        "recommendation_text": text,
    }

    op = UpdateOne(
        {"sensor_id": sensor_id, "vulnerability_category": category},
        {"$set": doc},
        upsert=True,
    )
    return op, action, reason, previous, rule


# ---------------------------------------------------------------------------
# Cycle entry point (will be registered with APScheduler in a later step)
# ---------------------------------------------------------------------------

async def run_recommendation_cycle() -> dict:
    """One full pass over (active sensors × vulnerability categories)."""
    started = _utc_now_naive()
    sensor_ids = await _discover_active_sensors()
    total_combos = len(sensor_ids) * len(VULNERABILITY_CATEGORIES)

    logger.info(
        "Recommendation cycle starting | sensors=%d categories=%d combinations=%d",
        len(sensor_ids),
        len(VULNERABILITY_CATEGORIES),
        total_combos,
    )

    metrics = {
        "combinations_total": total_combos,
        "regenerated": 0,
        "reused": 0,
        "skipped_no_forecast": 0,
        "errors": 0,
    }

    ops: List[UpdateOne] = []
    # Collected for the post-cycle alert dispatcher:
    #   (sensor_id, category, previous_doc, new_rule)
    transitions: List[Tuple[str, str, Optional[dict], RuleRecommendationResult]] = []

    for sensor_id in sensor_ids:
        pred_doc = await predictions().find_one({"sensor_id": sensor_id})
        forecast = (pred_doc or {}).get("predictions")
        if not forecast:
            metrics["skipped_no_forecast"] += len(VULNERABILITY_CATEGORIES)
            logger.warning(
                "No forecast for sensor=%s — skipping all categories", sensor_id
            )
            continue

        for category in VULNERABILITY_CATEGORIES:
            try:
                op, action, reason, prev, rule = await _process_combination(
                    sensor_id, category, forecast, started
                )
            except RecommendationError as e:
                metrics["errors"] += 1
                logger.error(
                    "Rule engine failed sensor=%s category=%s err=%s",
                    sensor_id, category, e,
                )
                continue
            except Exception as e:  # never crash the scheduler
                metrics["errors"] += 1
                logger.exception(
                    "Unexpected error sensor=%s category=%s err=%s",
                    sensor_id, category, e,
                )
                continue

            ops.append(op)
            transitions.append((sensor_id, category, prev, rule))
            if action == "regenerated":
                metrics["regenerated"] += 1
                logger.info(
                    "Regen sensor=%s category=%s reason=%s",
                    sensor_id, category, reason,
                )
            else:
                metrics["reused"] += 1
                logger.debug(
                    "Reuse sensor=%s category=%s reason=%s",
                    sensor_id, category, reason,
                )

    if ops:
        try:
            await dashboard_recommendations().bulk_write(ops, ordered=False)
        except BulkWriteError as bwe:
            logger.error(
                "dashboard_recommendations bulk_write failed: %s",
                (bwe.details or {}).get("writeErrors"),
            )

    # Post-write: detect urgency escalations and dispatch alerts.
    # Alert dispatch failure must NOT abort the recommendation cycle.
    alert_metrics = {}
    try:
        alert_metrics = await dispatch_alerts_for_cycle(transitions, now=started)
    except Exception as e:
        logger.exception("Alert dispatch crashed (continuing): %s", e)

    duration = (_utc_now_naive() - started).total_seconds()
    logger.info(
        "Recommendation cycle complete | total=%d regenerated=%d reused=%d "
        "skipped=%d errors=%d alerts_sent=%d duration=%.2fs",
        metrics["combinations_total"],
        metrics["regenerated"],
        metrics["reused"],
        metrics["skipped_no_forecast"],
        metrics["errors"],
        alert_metrics.get("users_notified", 0),
        duration,
    )
    metrics.update({f"alerts_{k}": v for k, v in alert_metrics.items()})
    return metrics


# ---------------------------------------------------------------------------
# Standalone runner (replaced by APScheduler-in-FastAPI in a later step)
# ---------------------------------------------------------------------------

async def _standalone_main() -> None:
    await connect_to_mongo()
    await ensure_dashboard_recommendations_indexes()
    # Make sure alert-related collections also have their indexes — the
    # standalone scheduler may run before / without the API.
    await ensure_notifications_indexes()
    await ensure_device_tokens_indexes()

    stop_event = asyncio.Event()

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    interval = settings.RECOMMENDATION_SCHEDULER_INTERVAL_SECONDS
    logger.info(
        "Recommendation scheduler standalone | interval=%ds | "
        "regen_interval_hours=%d | llm_base=%s | model=%s | "
        "llm_configured=%s",
        interval,
        settings.RECOMMENDATION_REGEN_INTERVAL_HOURS,
        settings.LLM_API_BASE_URL,
        settings.GROQ_MODEL,
        bool(settings.GROQ_API_KEY),
    )

    try:
        while not stop_event.is_set():
            try:
                await run_recommendation_cycle()
            except Exception as e:
                logger.exception("Recommendation cycle crashed (continuing): %s", e)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass
    finally:
        await close_mongo_connection()
        logger.info("Recommendation scheduler stopped")


if __name__ == "__main__":
    try:
        asyncio.run(_standalone_main())
    except KeyboardInterrupt:
        pass
