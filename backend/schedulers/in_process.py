"""
In-process scheduler.

Runs the forecast and recommendation cycles inside the FastAPI process via
APScheduler's `AsyncIOScheduler`. Each job is wrapped so a single failed
cycle never tears the scheduler down.

Enable by setting `ENABLE_IN_PROCESS_SCHEDULER=true` in your .env. The
standalone runners (`python -m schedulers.forecast_scheduler` and
`python -m schedulers.recommendation_scheduler`) keep working — use them
for testing, CI, or if you'd rather run schedulers as separate containers.

Jobs:
  - forecast       : every FORECAST_SCHEDULER_INTERVAL_SECONDS
  - recommendation : every RECOMMENDATION_SCHEDULER_INTERVAL_SECONDS,
                     offset by 2s so its first run sees the first
                     forecast's predictions
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.logger import get_logger
from schedulers.forecast_scheduler import run_forecast_cycle
from schedulers.recommendation_scheduler import run_recommendation_cycle

logger = get_logger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


# ---------------------------------------------------------------------------
# Job wrappers — never propagate exceptions to APScheduler
# ---------------------------------------------------------------------------

async def _wrapped_forecast() -> None:
    try:
        await run_forecast_cycle()
    except Exception as e:
        logger.exception("In-process forecast cycle failed (continuing): %s", e)


async def _wrapped_recommendation() -> None:
    try:
        await run_recommendation_cycle()
    except Exception as e:
        logger.exception("In-process recommendation cycle failed (continuing): %s", e)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def start_in_process_scheduler() -> None:
    """Build the AsyncIOScheduler and register the two recurring jobs."""
    global _scheduler
    if _scheduler is not None:
        logger.warning("In-process scheduler already started — skipping")
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")

    now = datetime.now(timezone.utc)

    _scheduler.add_job(
        _wrapped_forecast,
        trigger="interval",
        seconds=settings.FORECAST_SCHEDULER_INTERVAL_SECONDS,
        id="forecast_cycle",
        name="Forecast cycle",
        max_instances=1,     # never overlap a cycle with itself
        coalesce=True,       # if multiple runs are due, collapse to one
        next_run_time=now,   # fire ~immediately on startup
    )

    _scheduler.add_job(
        _wrapped_recommendation,
        trigger="interval",
        seconds=settings.RECOMMENDATION_SCHEDULER_INTERVAL_SECONDS,
        id="recommendation_cycle",
        name="Recommendation cycle",
        max_instances=1,
        coalesce=True,
        # Offset 2s so the first recommendation cycle reads the forecasts
        # produced by the first forecast cycle.
        next_run_time=now + timedelta(seconds=settings.FORECAST_SCHEDULER_INTERVAL_SECONDS * 0.5),
    )

    _scheduler.start()
    logger.info(
        "In-process scheduler started | forecast=%ds | recommendation=%ds",
        settings.FORECAST_SCHEDULER_INTERVAL_SECONDS,
        settings.RECOMMENDATION_SCHEDULER_INTERVAL_SECONDS,
    )


def stop_in_process_scheduler() -> None:
    """Shut down the scheduler. Safe to call even if it never started."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception as e:
        logger.warning("Scheduler shutdown raised: %s", e)
    _scheduler = None
    logger.info("In-process scheduler stopped")
