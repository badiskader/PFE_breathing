"""
Async MongoDB client (Motor) and collection accessors.

A single AsyncIOMotorClient is created per process. FastAPI calls
`connect_to_mongo()` on startup and `close_mongo_connection()` on shutdown.
Consumer/scheduler processes call the same helpers in their own event loop.
"""

from typing import Optional

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# Collection names — kept here so every module agrees on the spelling.
COLLECTION_SENSOR_READINGS = "sensor_readings"
COLLECTION_AQI_RESULTS = "aqi_results"
COLLECTION_PREDICTIONS = "predictions"
COLLECTION_USERS = "users"
COLLECTION_DASHBOARD_RECOMMENDATIONS = "dashboard_recommendations"
COLLECTION_CHAT_SESSIONS = "chat_sessions"
COLLECTION_KNOWLEDGE_CHUNKS = "knowledge_chunks"
COLLECTION_NOTIFICATIONS = "notifications"
COLLECTION_DEVICE_TOKENS = "device_tokens"


class _MongoState:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


_state = _MongoState()


async def connect_to_mongo() -> None:
    """Initialize the Mongo client. Idempotent."""
    if _state.client is not None:
        return

    logger.info("Connecting to MongoDB at %s", settings.MONGODB_URI)
    _state.client = AsyncIOMotorClient(settings.MONGODB_URI)
    _state.db = _state.client[settings.MONGODB_DATABASE]

    # Fail fast if the broker URI is bad.
    await _state.client.admin.command("ping")
    logger.info("MongoDB connection established (db=%s)", settings.MONGODB_DATABASE)


async def close_mongo_connection() -> None:
    if _state.client is None:
        return
    logger.info("Closing MongoDB connection")
    _state.client.close()
    _state.client = None
    _state.db = None


def get_db() -> AsyncIOMotorDatabase:
    if _state.db is None:
        raise RuntimeError(
            "MongoDB not connected. Call connect_to_mongo() during startup."
        )
    return _state.db


def get_collection(name: str) -> AsyncIOMotorCollection:
    return get_db()[name]


# --- Typed accessors (preferred entry points) ---

def sensor_readings() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_SENSOR_READINGS)


def aqi_results() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_AQI_RESULTS)


def predictions() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_PREDICTIONS)


def users() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_USERS)


def dashboard_recommendations() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_DASHBOARD_RECOMMENDATIONS)


def chat_sessions() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_CHAT_SESSIONS)


def knowledge_chunks() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_KNOWLEDGE_CHUNKS)


def notifications() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_NOTIFICATIONS)


def device_tokens() -> AsyncIOMotorCollection:
    return get_collection(COLLECTION_DEVICE_TOKENS)


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

async def ensure_sensor_readings_indexes() -> None:
    """
    Create indexes for `sensor_readings`. Idempotent — safe to call on every
    consumer startup.

    Index rationale
    ---------------
    Compound `(sensor_id, timestamp DESC)` serves two needs:
      1. Unique constraint → consumer re-deliveries don't create duplicates.
      2. Forecast scheduler reads "last 168 records per sensor sorted by
         timestamp desc" — this index serves that query directly.
    """
    coll = sensor_readings()
    await coll.create_index(
        [("sensor_id", 1), ("timestamp", -1)],
        unique=True,
        name="sensor_id_timestamp_unique",
    )
    logger.info("Ensured indexes on %s", COLLECTION_SENSOR_READINGS)


async def ensure_aqi_indexes() -> None:
    """
    Create indexes for `aqi_results`. Idempotent.

    Index rationale
    ---------------
    1. Unique compound `(sensor_id, timestamp DESC)`:
       - serves as the upsert key in the AQI consumer
       - serves "latest AQI per sensor" queries (GET /aqi/current)
       - serves per-sensor time-range queries (analytics)
    2. Plain descending `(timestamp DESC)`:
       - serves cross-sensor "what is the AQI fleet-wide right now?" queries
         (GET /aqi/sensors), which sort by timestamp without filtering by sensor.
    """
    coll = aqi_results()
    await coll.create_index(
        [("sensor_id", 1), ("timestamp", -1)],
        unique=True,
        name="sensor_id_timestamp_unique",
    )
    await coll.create_index(
        [("timestamp", -1)],
        name="timestamp_desc",
    )
    logger.info("Ensured indexes on %s", COLLECTION_AQI_RESULTS)


async def ensure_predictions_indexes() -> None:
    """
    Create indexes for `predictions`. Idempotent.

    Architecture stores ONE document per sensor (each forecast cycle
    overwrites the previous via upsert). Unique index on sensor_id enforces
    this invariant and serves the GET /predictions?sensor_id=X query.
    """
    coll = predictions()
    await coll.create_index(
        [("sensor_id", 1)],
        unique=True,
        name="sensor_id_unique",
    )
    await coll.create_index(
        [("generated_at", -1)],
        name="generated_at_desc",
    )
    logger.info("Ensured indexes on %s", COLLECTION_PREDICTIONS)


async def ensure_users_indexes() -> None:
    """Create indexes for `users`. Idempotent."""
    coll = users()
    await coll.create_index([("user_id", 1)], unique=True, name="user_id_unique")
    await coll.create_index(
        [("email", 1)],
        unique=True,
        sparse=True,  # multiple users without email are allowed
        name="email_unique",
    )
    logger.info("Ensured indexes on %s", COLLECTION_USERS)


async def ensure_chat_sessions_indexes() -> None:
    """Create indexes for `chat_sessions`. Idempotent."""
    coll = chat_sessions()
    await coll.create_index([("session_id", 1)], unique=True, name="session_id_unique")
    await coll.create_index([("user_id", 1), ("updated_at", -1)], name="user_id_updated_desc")
    logger.info("Ensured indexes on %s", COLLECTION_CHAT_SESSIONS)


async def ensure_knowledge_chunks_indexes() -> None:
    """Create indexes for `knowledge_chunks`. Idempotent.

    The vector index itself must be created OUT-OF-BAND in MongoDB Atlas
    (the `$vectorSearch` aggregation requires an Atlas Search index, which
    can only be defined via the Atlas UI / API, not via `create_index`).
    See `chatbot/seed_knowledge.py` for the Atlas index definition.
    """
    coll = knowledge_chunks()
    await coll.create_index([("chunk_id", 1)], unique=True, name="chunk_id_unique")
    await coll.create_index([("source", 1)], name="source")
    logger.info("Ensured indexes on %s", COLLECTION_KNOWLEDGE_CHUNKS)


async def ensure_notifications_indexes() -> None:
    """Create indexes for `notifications`. Idempotent.

    Read patterns served:
      - "list my N most recent notifications"      → (user_id, created_at DESC)
      - "what are my unread counts?"               → (user_id, read)
      - "have I been alerted on (sensor) recently" → (user_id, sensor_id, created_at DESC)
      - "mark by id"                               → unique (notification_id)
    """
    coll = notifications()
    await coll.create_index(
        [("notification_id", 1)],
        unique=True,
        name="notification_id_unique",
    )
    await coll.create_index(
        [("user_id", 1), ("created_at", -1)],
        name="user_recent",
    )
    await coll.create_index(
        [("user_id", 1), ("read", 1)],
        name="user_read",
    )
    await coll.create_index(
        [("user_id", 1), ("sensor_id", 1), ("created_at", -1)],
        name="user_sensor_recent",
    )
    logger.info("Ensured indexes on %s", COLLECTION_NOTIFICATIONS)


async def ensure_device_tokens_indexes() -> None:
    """Create indexes for `device_tokens`. Idempotent."""
    coll = device_tokens()
    await coll.create_index(
        [("expo_push_token", 1)],
        unique=True,
        name="token_unique",
    )
    await coll.create_index([("user_id", 1)], name="user_id")
    await coll.create_index([("user_id", 1), ("active", 1)], name="user_active")
    logger.info("Ensured indexes on %s", COLLECTION_DEVICE_TOKENS)


async def ensure_dashboard_recommendations_indexes() -> None:
    """
    Create indexes for `dashboard_recommendations`. Idempotent.

    Architecture stores ONE document per (sensor_id, vulnerability_category)
    combination. The unique index enforces this invariant and serves the
    primary read pattern:
      GET /recommendations/dashboard → find by (sensor_id, category)
    A secondary index supports admin queries like
      "show all recommendations for category=vulnérable, latest first".
    """
    coll = dashboard_recommendations()
    await coll.create_index(
        [("sensor_id", 1), ("vulnerability_category", 1)],
        unique=True,
        name="sensor_id_category_unique",
    )
    await coll.create_index(
        [("vulnerability_category", 1), ("generated_at", -1)],
        name="category_generated_at_desc",
    )
    logger.info("Ensured indexes on %s", COLLECTION_DASHBOARD_RECOMMENDATIONS)
