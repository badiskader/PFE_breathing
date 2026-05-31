"""
Centralized configuration loaded from environment variables.

Every other module imports `settings` from here. No hardcoded URLs,
credentials, or paths are allowed elsewhere in the codebase.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Kafka ---
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_SENSOR_RAW: str = "sensor-raw"
    KAFKA_CONSUMER_GROUP_AQI: str = "aqi-evaluator-group"
    KAFKA_CONSUMER_GROUP_RAW: str = "raw-writer-group"
    KAFKA_CONSUMER_GROUP_LAKEHOUSE: str = "lakehouse-writer-group"

    # --- MongoDB ---
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "airquality"

    # --- Mamba forecasting API ---
    # The model expects FULL raw records (location + pollutants + weather) and
    # performs all preprocessing internally. The backend is a pure orchestrator.
    MAMBA_API_URL: str = "http://localhost:9000/predict_raw"
    MAMBA_API_TIMEOUT_SECONDS: int = 60

    # --- Forecast scheduler ---
    FORECAST_WINDOW_SIZE: int = 168              # raw records sent per sensor
    FORECAST_HORIZON_HOURS: int = 12             # hours returned by Mamba
    FORECAST_SCHEDULER_INTERVAL_SECONDS: int = 5 # matches SIMULATION_TICK_SECONDS

    # --- LLM (Groq today; OpenAI-compatible API) ---
    # Swappable by changing LLM_API_BASE_URL:
    #   Groq:    https://api.groq.com/openai/v1
    #   OpenAI:  https://api.openai.com/v1
    #   Ollama:  http://localhost:11434/v1
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    LLM_API_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_TIMEOUT_SECONDS: int = 30

    # --- Recommendation scheduler ---
    RECOMMENDATION_SCHEDULER_INTERVAL_SECONDS: int = 15

    # --- In-process scheduler (APScheduler inside FastAPI) ---
    # When true, the FastAPI process runs the forecast + recommendation
    # cycles itself, so you don't need separate
    # `python -m schedulers.*` processes. Standalone runners still work.
    ENABLE_IN_PROCESS_SCHEDULER: bool = False

    # --- Alerts / notifications ---
    # Lowest urgency that triggers a push: safe < caution < avoid < danger.
    # Only escalations to ≥ this level fire a notification.
    ALERT_URGENCY_THRESHOLD: str = "avoid"
    # Don't notify the same (user, sensor) pair more than once per N hours.
    ALERT_COOLDOWN_HOURS: int = 1
    # Default UI language for templated notification text when the user
    # has no notification_preferences.language set.
    ALERT_DEFAULT_LANGUAGE: str = "fr"
    # Expo Push v2 endpoint (overridable for self-hosted Expo or tests).
    EXPO_PUSH_URL: str = "https://exp.host/--/api/v2/push/send"
    EXPO_PUSH_TIMEOUT_SECONDS: int = 15

    # --- Chatbot ---
    # How many prior messages of the session are passed to the LLM as context.
    CHAT_HISTORY_WINDOW: int = 10
    # Cap messages persisted per session (older ones dropped via $slice on push).
    CHAT_MAX_MESSAGES_PER_SESSION: int = 200
    # Top-K chunks retrieved per RAG query.
    RAG_TOP_K: int = 5
    # If true, retrieval uses MongoDB Atlas $vectorSearch (production).
    # If false, retrieval falls back to in-Python cosine similarity over the
    # full `knowledge_chunks` collection — works on a local single-node Mongo
    # and is fine for thesis-scale knowledge bases (<10k chunks).
    USE_ATLAS_VECTOR_SEARCH: bool = True
    ATLAS_VECTOR_INDEX_NAME: str = "knowledge_chunks_vector_index"

    # --- Embeddings ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- Storage paths ---
    LAKEHOUSE_PATH: str = "./data/lakehouse"
    CSV_DATA_PATH: str = "./data/raw_csv"

    # --- Lakehouse writer ---
    # Flush the in-memory batch when EITHER threshold is hit.
    LAKEHOUSE_BATCH_SIZE: int = 200
    LAKEHOUSE_FLUSH_INTERVAL_SECONDS: int = 30

    # --- Simulation ---
    SIMULATION_TICK_SECONDS: int = 5
    ACTIVE_SENSOR_IDS: Optional[str] = None  # CSV string; None = all 38 sensors
    PRODUCER_LOOP_ON_EOF: bool = True  # restart from row 0 when CSVs are exhausted

    # --- Recommendation reuse logic ---
    RECOMMENDATION_REGEN_INTERVAL_HOURS: int = 3

    # --- Auth ---
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    # Registered users: short-ish access tokens (no refresh-token flow yet).
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7    # 7 days
    # Guests don't have credentials to log back in with, so their tokens live longer.
    JWT_GUEST_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30    # 30 days

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return upper

    @property
    def active_sensor_ids(self) -> Optional[List[str]]:
        """Parsed ACTIVE_SENSOR_IDS. None means: use all sensors."""
        if not self.ACTIVE_SENSOR_IDS:
            return None
        return [s.strip() for s in self.ACTIVE_SENSOR_IDS.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
