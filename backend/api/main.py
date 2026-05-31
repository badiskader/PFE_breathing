"""
FastAPI application entry point.

Thin REST layer over MongoDB. The app does NOT consume from Kafka, call
Mamba, or call Groq — all heavy work runs in upstream
consumer/scheduler processes. The API only reads pre-computed data.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import (
    analytics,
    aqi,
    auth,
    chat,
    notifications,
    predictions,
    recommendations,
    sensors,
    users,
)
from core.config import settings
from core.logger import get_logger
from schedulers.in_process import (
    start_in_process_scheduler,
    stop_in_process_scheduler,
)
from core.mongo_client import (
    close_mongo_connection,
    connect_to_mongo,
    ensure_aqi_indexes,
    ensure_chat_sessions_indexes,
    ensure_dashboard_recommendations_indexes,
    ensure_device_tokens_indexes,
    ensure_knowledge_chunks_indexes,
    ensure_notifications_indexes,
    ensure_predictions_indexes,
    ensure_sensor_readings_indexes,
    ensure_users_indexes,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: connect Mongo + ensure all indexes
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI starting — connecting MongoDB and ensuring indexes")
    await connect_to_mongo()
    await ensure_sensor_readings_indexes()
    await ensure_aqi_indexes()
    await ensure_predictions_indexes()
    await ensure_dashboard_recommendations_indexes()
    await ensure_users_indexes()
    await ensure_chat_sessions_indexes()
    await ensure_knowledge_chunks_indexes()
    await ensure_notifications_indexes()
    await ensure_device_tokens_indexes()
    # In-process scheduler (optional — controlled by ENABLE_IN_PROCESS_SCHEDULER).
    if settings.ENABLE_IN_PROCESS_SCHEDULER:
        start_in_process_scheduler()

    logger.info(
        "FastAPI ready | mongo connected | %d routers registered | "
        "in_process_scheduler=%s",
        len(app.routes),
        settings.ENABLE_IN_PROCESS_SCHEDULER,
    )
    yield
    logger.info("FastAPI shutting down — stopping scheduler and closing MongoDB")
    if settings.ENABLE_IN_PROCESS_SCHEDULER:
        stop_in_process_scheduler()
    await close_mongo_connection()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI-IoT Air Quality Monitoring & Personalized Recommendation API",
    version="0.1.0",
    description=(
        "REST API for the master's thesis prototype.\n\n"
        "Read-only access to pre-computed AQI, forecasts, and personalized "
        "recommendations. All heavy computation runs in the upstream "
        "Kafka consumers and APScheduler-driven jobs."
    ),
    lifespan=lifespan,
)

# CORS — permissive for the thesis demo (mobile app, Swagger, Postman).
# Production deployment would restrict origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"], summary="Liveness probe")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sensors.router)
app.include_router(aqi.router)
app.include_router(predictions.router)
app.include_router(recommendations.router)
app.include_router(analytics.router)
app.include_router(chat.router)
app.include_router(notifications.router)


# ---------------------------------------------------------------------------
# Global exception handler — never expose stack traces to clients
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception | method=%s url=%s err=%s",
        request.method,
        request.url,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
