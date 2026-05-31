# AirPulse Backend — Technical Handoff

**Audience**: a developer continuing this project in a new session with no prior context.
**Scope**: full state of the backend at the end of Step 12 of the 13-step build plan.
**Companion artifacts** (on the user's machine, outside the repo):
- `C:\Users\kizmo\Downloads\thesis_backend_context (2).txt` — original architecture brief.
- `C:\Users\kizmo\Downloads\thesis_frontend_context_v4.txt` — frontend brief aligned to actual backend shapes.

---

## 1. Project Overview

### What this backend does

This is the backend of a master's-thesis prototype: an **AI-IoT air-quality monitoring and personalized health recommendation platform** (frontend app name: **AirPulse**). It implements the full pipeline from simulated IoT sensor data through to a mobile-facing REST API:

1. **Stream simulation** — replays a historical CSV dataset over Kafka at 1 simulated hour per 5 real seconds.
2. **Real-time persistence** — writes raw observations to MongoDB and a Parquet lakehouse simultaneously.
3. **Real-time AQI** — computes US EPA AQI from pollutants in real time and stores results in MongoDB.
4. **Forecasting** — every simulated hour, sends the last 168 hours of observations per sensor to an external **Mamba-SSM** model via HTTP and stores the 12-hour pollutant forecast.
5. **Type-1 personalized recommendations** — every cycle, runs a deterministic rule engine + Groq LLM per `(sensor × vulnerability_category)`, with smart-regen caching.
6. **Alerts** — when the rule engine detects an urgency escalation, sends Expo push notifications to opted-in users (with cooldown + quiet-hours gating).
7. **Multi-agent RAG chatbot** — Agno `Team` (mode="coordinate") with three specialist agents (PersonalAdvisor, Analytics, Knowledge) backed by sentence-transformers + Atlas Vector Search (with local-cosine fallback).
8. **REST API** — FastAPI exposes all of the above to a React Native mobile app.
9. **Lakehouse analytics** — DuckDB queries on Parquet for trend / worst-day / sensor-comparison endpoints.

### Tech stack

| Layer | Library | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Web framework | FastAPI | 0.115.6 |
| ASGI server | uvicorn[standard] | 0.32.1 |
| Validation | pydantic | 2.10.4 |
| Settings | pydantic-settings | 2.7.0 |
| Async Mongo | motor / pymongo | 3.6.0 / 4.9.2 |
| Async Kafka | aiokafka | 0.12.0 |
| HTTP client | httpx | 0.28.1 |
| Scheduling | APScheduler | 3.11.0 |
| Data / lakehouse | pandas / pyarrow / duckdb | 2.2.3 / 18.1.0 / 1.1.3 |
| Embeddings | sentence-transformers | 3.3.1 |
| Multi-agent | agno | ≥1.0.0 |
| PDF ingestion | pypdf | ≥4.0.0 |
| Auth | python-jose / bcrypt (direct) | 3.3.0 / ≥4.0, <5.0 |
| Containerization | Docker Compose | — |

> `passlib` is in `requirements.txt` (transitive) but **not imported** by our code — `services/auth_service.py` talks to bcrypt directly to avoid a version-detection bug with `bcrypt>=4.1`.

### Project structure

```
backend/
├── core/                          # foundation — imported by everything
│   ├── config.py                  # Pydantic Settings; ALL env vars
│   ├── logger.py                  # shared logger factory
│   ├── mongo_client.py            # Motor client + typed accessors + index helpers
│   └── kafka_client.py            # aiokafka producer/consumer factories
│
├── streaming/                     # IoT simulator
│   ├── producer.py                # CSV replay → sensor-raw Kafka topic
│   └── schemas.py                 # SensorEvent + feature constants
│                                  #   (POLLUTANT_COLUMNS, WEATHER_COLUMNS,
│                                  #    LOCATION_COLUMNS, FORECAST_FEATURE_COLUMNS,
│                                  #    AQI_FEATURE_COLUMNS)
│
├── consumers/                     # Kafka consumers (3 independent groups)
│   ├── raw_writer_consumer.py     # → MongoDB sensor_readings
│   ├── aqi_consumer.py            # → MongoDB aqi_results (real-time AQI)
│   └── lakehouse_writer.py        # → Parquet date-partitioned files
│
├── services/                      # pure business logic — no I/O wiring
│   ├── aqi_service.py             # US EPA AQI breakpoints + computation
│   ├── forecast_service.py        # Mamba HTTP client + payload/response shaping
│   ├── recommendation_engine.py   # vulnerability category, rule engine, Type 1+2
│   ├── alert_dispatcher.py        # urgency-escalation detection + push dispatch
│   ├── llm_client.py              # shared OpenAI-compatible chat-completion HTTP
│   ├── push_client.py             # Expo Push Notification API
│   └── auth_service.py            # bcrypt + JWT encode/decode
│
├── schedulers/                    # periodic jobs
│   ├── forecast_scheduler.py      # standalone runner + run_forecast_cycle()
│   ├── recommendation_scheduler.py # standalone runner + run_recommendation_cycle()
│   └── in_process.py              # APScheduler wiring for in-FastAPI mode
│
├── lakehouse/                     # Parquet bronze layer + DuckDB queries
│   ├── writer.py                  # LakehouseBatchWriter (date-partitioned)
│   └── query_engine.py            # LakehouseQueryEngine (DuckDB on Parquet)
│
├── api/                           # FastAPI app
│   ├── main.py                    # app, lifespan, CORS, exception handler
│   ├── dependencies.py            # DI: collection accessors + JWT
│   └── routers/
│       ├── auth.py                # /auth/register, /auth/login, /auth/guest
│       ├── users.py               # /users/me, /users/onboarding
│       ├── sensors.py             # /sensors (public — list with coords)
│       ├── aqi.py                 # /aqi/current, /aqi/sensors (enriched)
│       ├── predictions.py         # /predictions
│       ├── recommendations.py     # /recommendations/dashboard
│       ├── analytics.py           # /analytics/{trend, worst-day, sensor-comparison}
│       ├── chat.py                # POST /chat, GET /chat/{sid}/history
│       └── notifications.py       # /devices/* + /notifications/*
│
├── chatbot/                       # multi-agent RAG (Agno-based)
│   ├── orchestrator.py            # handle_message — thin wrapper around the Team
│   ├── team.py                    # 3 Agno Agents + Team in 'coordinate' mode
│   ├── tools.py                   # Agno-callable async tool functions
│   ├── context.py                 # orchestrator helpers (nearest sensor, history)
│   ├── session_manager.py         # Mongo-backed conversation memory
│   ├── retriever.py               # Atlas $vectorSearch + local cosine fallback
│   ├── embedder.py                # sentence-transformers (lazy singleton)
│   ├── seed_knowledge.py          # CLI: seed 16 hand-curated chunks
│   └── ingest_pdfs.py             # CLI: ingest a directory of PDFs
│
├── data/                          # local data (should be gitignored)
│   ├── raw_csv/                   # input dataset (one CSV per sensor)
│   └── lakehouse/                 # Parquet bronze files
│
├── docker/
│   ├── docker-compose.yml         # Zookeeper, Kafka, Mongo, API, producer,
│   │                              # raw_writer, aqi_consumer, lakehouse_writer,
│   │                              # recommendation_scheduler
│   ├── Dockerfile.api             # single image used for all Python services
│   └── .env.example               # env var template
│
├── .env                           # actual env (gitignored) — lives at backend/
├── mock_mamba.py                  # dev stand-in for the real Mamba container
├── requirements.txt
└── HANDOFF.md                     # this file
```

---

## 2. Architecture & Design Decisions

### Overall pattern

**Event-driven streaming + REST API + sidecar schedulers.** No microservice mesh — each concern is a Python module run as its own process (consumer, scheduler, API). Composition by Docker Compose. Layered code organization: `core/` → `services/` (pure logic) → `consumers/` + `schedulers/` + `api/` (I/O wiring).

```
                         ┌─────────────────┐    ┌────────────────────┐
                         │  raw_writer     │───►│ sensor_readings    │
                         └─────────────────┘    └────────────────────┘
                                  ▲
                                  │
┌──────────┐    Kafka            ├─┌─────────────────┐    ┌────────────────────┐
│ producer │───►(sensor-raw)─────┼►│  aqi_consumer   │───►│ aqi_results        │
│ (CSV)    │                     │ └─────────────────┘    └────────────────────┘
└──────────┘                     │
                                  └─┌─────────────────┐    ┌────────────────────┐
                                    │ lakehouse_writer│───►│ data/lakehouse/    │
                                    └─────────────────┘    │   date=YYYY-MM-DD/ │
                                                           │     batch_*.parquet│
                                                           └────────────────────┘

  forecast_scheduler ── HTTP ──► Mamba container ──► predictions collection
                                                          │
                                                          ▼
                                  recommendation_scheduler ──► dashboard_recommendations
                                                          │
                                                          ▼
                                                  alert_dispatcher ──► Expo Push
                                                                       notifications collection

  FastAPI ─── reads ───► all Mongo collections + DuckDB on Parquet
          ─── /chat ──► Agno Team ──► tools (Mongo, retriever) + Groq LLM
```

### Key design decisions

| Decision | Why |
|---|---|
| **`sensor_readings` is the canonical raw observation store** (15 fields incl. weather) | Forecasting and analytics need the full raw record. Subsets are selected via constants in `streaming/schemas.py` — no downstream layer reshapes the raw event. |
| **Three independent Kafka consumer groups** | Each downstream concern (raw persist, AQI compute, lakehouse) consumes the same topic without contention. Adding a fourth is one config line. |
| **One AQI service shared across streaming AND analytics** | Same `compute_sub_index` runs in `aqi_consumer` (real-time) and in `lakehouse/query_engine` (analytics on Parquet). Single source of truth for the EPA formula. |
| **Rule engine + LLM split (Layer A / Layer B)** | Recommendation logic is auditable Python (`rule_output` in JSON); the LLM only narrates. Same `compute_rule_based_recommendation` is invoked for Type 1 (dashboard scheduler) and Type 2 (chatbot personal advisor). |
| **Smart-regen for Type 1** | LLM only fires when urgency or AQI category changes, or 3 hours elapsed. Cuts Groq calls by orders of magnitude. |
| **Agno `Team` in `coordinate` mode** | Semantic routing + multi-agent collaboration for compound questions. Three agents (PersonalAdvisor, Analytics, Knowledge); compound questions run multiple in parallel and the leader merges. |
| **Pre-fetched AQI snapshot per chat turn** | The orchestrator fetches once and injects via Agno `additional_context`; agents don't redundantly call `get_current_air_quality`. |
| **JWT auth with first-class guest accounts** | `POST /auth/guest` creates a real user document (`is_guest=true`, `vulnerability_category="générale"`) and issues a 30-day token. Downstream code treats guests uniformly. |
| **bcrypt called directly (no passlib)** | `passlib`'s bcrypt backend breaks with `bcrypt>=4.1` (`AttributeError: __about__`). Talking to bcrypt directly avoids version detection entirely. |
| **In-process APScheduler is OPTIONAL** | `ENABLE_IN_PROCESS_SCHEDULER=true` collapses three processes (forecast, reco, FastAPI) into one. Standalone runners stay for testing/CI. |
| **Local cosine fallback for vector search** | The retriever works on local single-node Mongo (no Atlas required) by computing cosine in Python. Flip `USE_ATLAS_VECTOR_SEARCH=true` to switch to `$vectorSearch`. |
| **Hive-partitioned Parquet (no single-file append)** | Each flush writes a NEW `date=YYYY-MM-DD/batch_<uuid>.parquet`. DuckDB reads the whole directory via `read_parquet(..., hive_partitioning=1)`. |
| **Cooldown / quiet-hours / opt-in checks at dispatch time** | The alert dispatcher records every alert in the `notifications` collection BEFORE attempting an Expo push so the in-app notification center works even without registered device tokens (useful for thesis demo). |

### External services

| Service | Purpose | How |
|---|---|---|
| **Mamba forecast API** | 12-hour pollutant forecast | `POST` full 168×N raw records (no preprocessing), get 12 pollutant rows back. URL via `MAMBA_API_URL`. |
| **Groq (or any OpenAI-compatible)** | LLM for recommendation text + chatbot replies | `services/llm_client.py`. Provider swap = change `LLM_API_BASE_URL` (Groq → OpenAI → Ollama). |
| **Expo Push Notification service** | Push delivery to phones | `services/push_client.py`. URL: `https://exp.host/--/api/v2/push/send`. No API key required for basic use. |
| **MongoDB Atlas Vector Search** (optional) | Production RAG | Auto-used when `USE_ATLAS_VECTOR_SEARCH=true` and Atlas index exists. Falls back to local cosine on failure. |

---

## 3. Environment & Configuration

### `.env` file location

**`backend/.env`** (NOT `backend/docker/.env`). The producer/consumers/schedulers/API all read from cwd when launched, and `core/config.py`'s pydantic-settings does `env_file=".env"`.
A template lives at `backend/docker/.env.example` — copy it to `backend/.env` and edit.

### Full env var reference

| Variable | Purpose | Default |
|---|---|---|
| **Kafka** | | |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker(s) | `localhost:9092` (Docker) / `localhost:29092` (host) |
| `KAFKA_TOPIC_SENSOR_RAW` | Topic for sensor events | `sensor-raw` |
| `KAFKA_CONSUMER_GROUP_AQI` | AQI consumer group id | `aqi-evaluator-group` |
| `KAFKA_CONSUMER_GROUP_RAW` | Raw writer consumer group | `raw-writer-group` |
| `KAFKA_CONSUMER_GROUP_LAKEHOUSE` | Lakehouse writer consumer group | `lakehouse-writer-group` |
| **MongoDB** | | |
| `MONGODB_URI` | Mongo connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | DB name | `airquality` |
| **Mamba forecast API** | | |
| `MAMBA_API_URL` | Mamba endpoint | `http://localhost:9000/predict_raw` (real model in dev) |
| `MAMBA_API_TIMEOUT_SECONDS` | HTTP timeout | `60` |
| **Forecast scheduler** | | |
| `FORECAST_WINDOW_SIZE` | Records per sensor sent to Mamba | `168` |
| `FORECAST_HORIZON_HOURS` | Hours returned by Mamba | `12` |
| `FORECAST_SCHEDULER_INTERVAL_SECONDS` | How often to forecast | `5` (= 1 simulated hour) |
| **LLM** | | |
| `GROQ_API_KEY` | API key (Groq today) | None → LLM unavailable → fallback text |
| `GROQ_MODEL` | Model id | `llama-3.3-70b-versatile` |
| `LLM_API_BASE_URL` | OpenAI-compat base URL | `https://api.groq.com/openai/v1` |
| `LLM_TIMEOUT_SECONDS` | HTTP timeout | `30` |
| **Recommendation scheduler** | | |
| `RECOMMENDATION_SCHEDULER_INTERVAL_SECONDS` | Cycle interval | `15` |
| `RECOMMENDATION_REGEN_INTERVAL_HOURS` | Force-regen interval | `3` |
| **Alerts / notifications** | | |
| `ALERT_URGENCY_THRESHOLD` | Lowest urgency that fires a push (`safe`/`caution`/`avoid`/`danger`) | `avoid` |
| `ALERT_COOLDOWN_HOURS` | Per `(user, sensor)` cooldown | `1` |
| `ALERT_DEFAULT_LANGUAGE` | Fallback language for templates | `fr` |
| `EXPO_PUSH_URL` | Expo push endpoint | `https://exp.host/--/api/v2/push/send` |
| `EXPO_PUSH_TIMEOUT_SECONDS` | HTTP timeout | `15` |
| **Chatbot** | | |
| `CHAT_HISTORY_WINDOW` | Recent messages injected into LLM context | `10` |
| `CHAT_MAX_MESSAGES_PER_SESSION` | Storage cap per session (`$slice`) | `200` |
| `RAG_TOP_K` | Top chunks per RAG query | `5` |
| `USE_ATLAS_VECTOR_SEARCH` | Use Atlas `$vectorSearch` if true; else local cosine | `false` |
| `ATLAS_VECTOR_INDEX_NAME` | Atlas Search index name | `knowledge_chunks_vector_index` |
| **Embeddings** | | |
| `EMBEDDING_MODEL` | sentence-transformers model id | `all-MiniLM-L6-v2` (384-dim) |
| **Storage / simulation** | | |
| `LAKEHOUSE_PATH` | Parquet root dir | `./data/lakehouse` |
| `CSV_DATA_PATH` | Input CSV dir | `./data/raw_csv` |
| `LAKEHOUSE_BATCH_SIZE` | Flush after N rows | `200` |
| `LAKEHOUSE_FLUSH_INTERVAL_SECONDS` | Flush after N seconds | `30` |
| `SIMULATION_TICK_SECONDS` | Producer cadence | `5` |
| `ACTIVE_SENSOR_IDS` | Comma-separated subset (empty = all) | empty |
| `PRODUCER_LOOP_ON_EOF` | Restart from row 0 at EOF | `true` |
| **In-process scheduler** | | |
| `ENABLE_IN_PROCESS_SCHEDULER` | Run forecast + reco inside FastAPI | `false` |
| **Auth** | | |
| `JWT_SECRET_KEY` | HS256 signing secret | `change-me-in-production` |
| `JWT_ALGORITHM` | JWT alg | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Registered token expiry | `10080` (7 days) |
| `JWT_GUEST_TOKEN_EXPIRE_MINUTES` | Guest token expiry | `43200` (30 days) |
| **Logging** | | |
| `LOG_LEVEL` | DEBUG/INFO/WARNING/... | `INFO` |

### Config files

- `core/config.py` — the single Python place where settings are read. Every other module does `from core.config import settings`.
- `docker/docker-compose.yml` — orchestrates Zookeeper, Kafka, Mongo, API, producer, raw_writer, aqi_consumer, lakehouse_writer, recommendation_scheduler.
- `docker/Dockerfile.api` — same image used for every Python service; the per-service command is set in compose.

### Run the project locally (PowerShell)

Prerequisites: Docker Desktop, Python 3.11+, your real Mamba container running.

```powershell
# 1. Venv + deps
cd C:\Users\kizmo\OneDrive\Desktop\school\PFE\Air_quality_recommendation\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Create backend/.env from the template; set at least:
#    KAFKA_BOOTSTRAP_SERVERS=localhost:29092   (host) or kafka:9092 (Docker)
#    MONGODB_URI=mongodb://localhost:27017
#    MAMBA_API_URL=http://localhost:9000/predict_raw   (or wherever your Mamba is)
#    GROQ_API_KEY=<your key>
Copy-Item docker\.env.example .env

# 3. Bring up infrastructure
cd docker
docker compose up -d zookeeper kafka mongo
docker compose ps    # all healthy

# 4. Run each service in its own terminal (cd backend, activate venv first)
python -m streaming.producer
python -m consumers.raw_writer_consumer
python -m consumers.aqi_consumer
python -m consumers.lakehouse_writer
python -m schedulers.forecast_scheduler
python -m schedulers.recommendation_scheduler
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# OR, simplified: set ENABLE_IN_PROCESS_SCHEDULER=true in .env and skip the
# two scheduler terminals — uvicorn runs both cycles via APScheduler.
```

> **Ports**: Mamba uses 8000 (or 9000), so FastAPI is on **8080**. Kafka exposes both `9092` (in-Docker) and `29092` (from host).

---

## 4. Database

### Engine

**MongoDB 7.0**, async via **Motor 3.6**. No ORM — collections accessed through typed helpers in `core/mongo_client.py`.

### Connection lifecycle

Single `AsyncIOMotorClient` per process, opened in `connect_to_mongo()` and closed in `close_mongo_connection()`. FastAPI calls these in its lifespan; consumers/schedulers do the same in their `_standalone_main()`.

### Collections

#### `sensor_readings` — canonical raw observation store

```javascript
{
  _id: ObjectId,
  sensor_id: str,
  timestamp: datetime,            // BSON date

  // location (3)
  latitude: float,
  longitude: float,
  sensor_radius_km: float,

  // pollutants (6) — µg/m³
  PM25, PM10, NO2, SO2, CO, O3: float,

  // weather (4)
  temperature_2m: float,          // °C
  relative_humidity_2m: float,    // %
  wind_speed_10m: float,          // m/s
  wind_direction_10m: float       // degrees 0-360
}
```
**Indexes**: unique compound `(sensor_id ASC, timestamp DESC)` — also serves "last N records per sensor".

#### `aqi_results`

```javascript
{
  _id: ObjectId,
  sensor_id: str,
  timestamp: datetime,
  aqi_score: int,                  // 0-500
  aqi_category: str,               // "Good"|"Moderate"|"Unhealthy for Sensitive Groups"|...
  risk_level: str,                 // "low"|"moderate"|"high"|"very_high"|"severe"
  dominant_pollutant: str,         // "PM25"|"PM10"|"NO2"|"SO2"|"CO"|"O3"
  sub_indices: { PM25: int, PM10: int, NO2: int, SO2: int, CO: int, O3: int }
}
```
**Indexes**: unique `(sensor_id ASC, timestamp DESC)`, plus `(timestamp DESC)`.

#### `predictions`

One document per sensor, upserted each forecast cycle.
```javascript
{
  sensor_id: str,
  generated_at: datetime,
  forecast_horizon_hours: 12,
  predictions: [
    {
      hour_offset: 1..12,
      timestamp: datetime,
      PM25, PM10, NO2, SO2, CO, O3: float,
      predicted_aqi: int,
      predicted_category: str
    }
  ]
}
```
**Indexes**: unique `(sensor_id)`, plus `(generated_at DESC)`.

#### `users`

```javascript
{
  user_id: str,                              // "user_<hex>" or "guest_<hex>"
  email: str | absent,                       // unique sparse
  hashed_password: str | absent,             // bcrypt; only for registered users
  name: str | null,
  is_guest: bool,
  device_id: str | null,                     // for guests
  vulnerability_category: "générale"|"sensible"|"vulnérable",
  vulnerability_score: float,                // 0-1
  vulnerability_factors: [str],
  onboarding_completed: bool,
  profile_last_updated: datetime | null,
  created_at: datetime,
  profile: {
    age, gender, chronic_diseases, asthma, cardiovascular, allergies,
    smoking_status, activity_level, pollution_sensitivity, preferred_locations,
    is_pregnant, outdoor_worker, intense_sport, low_socioeconomic
  } | absent,
  notification_preferences: {                // optional, defaults applied at read time
    aqi_alerts_enabled, forecast_alerts_enabled, recommendation_alerts_enabled,
    daily_summary_enabled, language, quiet_hours: { enabled, start, end }
  } | absent
}
```
**Indexes**: unique `(user_id)`, unique sparse `(email)`.

#### `dashboard_recommendations`

```javascript
{
  sensor_id: str,
  vulnerability_category: str,
  generated_at: datetime,
  forecast_aqi_max: int,
  forecast_category: str,
  rule_output: {
    vulnerability_category, forecast_aqi_max, forecast_category,
    aqi_trajectory: "rising"|"stable"|"falling",
    flagged_pollutants: [str],
    urgency_level: "safe"|"caution"|"avoid"|"danger",
    key_risks: [str],
    pollutant_scores: { <pollutant>: 0..3 },
    pollutant_max_values: { <pollutant>: float }
  },
  recommendation_text: str
}
```
**Indexes**: unique `(sensor_id, vulnerability_category)`, plus `(vulnerability_category, generated_at DESC)`.

#### `chat_sessions`

```javascript
{
  session_id: str,                  // uuid4 hex
  user_id: str,
  created_at: datetime,
  updated_at: datetime,
  messages: [
    { role: "user"|"assistant", content: str, timestamp: datetime,
      agent_used: str | null }
  ]
}
```
**Indexes**: unique `(session_id)`, plus `(user_id, updated_at DESC)`.
Capped via `$slice: -CHAT_MAX_MESSAGES_PER_SESSION` on every push.

#### `knowledge_chunks`

```javascript
{
  chunk_id: str,                    // unique; "<source>_p<NNNN>" for PDFs
  source: str,                      // doc title / pdf stem
  content: str,                     // raw text
  embedding: [float; 384],          // all-MiniLM-L6-v2
  updated_at: datetime
}
```
**Indexes**: unique `(chunk_id)`, `(source)`.
**Atlas vector index** (created out-of-band in Atlas UI):
```json
{ "fields": [
  { "type": "vector", "path": "embedding",
    "numDimensions": 384, "similarity": "cosine" } ] }
```

#### `notifications`

```javascript
{
  notification_id: str,             // "notif_<hex>"
  user_id: str,
  type: "recommendation_alert"|"aqi_alert"|"forecast_alert"|"system"|"daily_summary",
  title: str,
  body: str,
  severity: "safe"|"caution"|"avoid"|"danger",
  sensor_id: str | null,
  created_at: datetime,
  read: bool,
  read_at: datetime | absent,
  data: {                            // deep-link payload
    screen, sensor_id, forecast_category, urgency_level, flagged_pollutants
  }
}
```
**Indexes**: unique `(notification_id)`; `(user_id, created_at DESC)`; `(user_id, read)`; `(user_id, sensor_id, created_at DESC)`.

#### `device_tokens`

```javascript
{
  user_id: str,
  expo_push_token: str,              // unique
  platform: str,                     // "ios"|"android"|"web"
  device_id: str | null,
  app_version: str | null,
  active: bool,
  registered_at: datetime,
  updated_at: datetime,
  deactivated_at: datetime | absent
}
```
**Indexes**: unique `(expo_push_token)`; `(user_id)`; `(user_id, active)`.

### Migrations / seed data

- **No migration framework.** Indexes created idempotently at process startup via `ensure_*_indexes()` helpers in `core/mongo_client.py`. FastAPI lifespan calls each; standalone consumers/schedulers call only the ones they need.
- **Seed KB**: `python -m chatbot.seed_knowledge` upserts 16 hand-curated chunks.
- **Real PDF KB**: `python -m chatbot.ingest_pdfs <pdf_dir>` extracts → chunks → embeds → upserts.
- **Sensor data**: not auto-seeded — the user supplies CSVs in `data/raw_csv/`; the producer streams them.

---

## 5. Authentication & Authorization

### Mechanism

**JWT (HS256)** in `Authorization: Bearer <token>` header. No sessions, no cookies.

### Token shape

```json
{ "sub": "<user_id>", "is_guest": true|false, "iat": <ts>, "exp": <ts> }
```

### Issuing

| Endpoint | What happens |
|---|---|
| `POST /auth/register` | bcrypt-hashes password (max 72 bytes), inserts user doc, returns JWT (7 days). |
| `POST /auth/login` | Verifies bcrypt hash; returns JWT (7 days). |
| `POST /auth/guest` | Creates user with `is_guest=true`, `vulnerability_category="générale"`, `onboarding_completed=true`; returns JWT (30 days). |

### Verification

`api/dependencies.py` exposes three dependencies for routers:

- **`get_current_user_id`** — REQUIRED; raises 401 if missing/invalid.
- **`get_current_user_id_optional`** — returns `None` instead of raising (for endpoints that work anonymously).
- **`get_current_token_claims`** — full payload (for `is_guest` checks).

### Refresh / revoke

**Not implemented.** Token expiry is the only revocation. For production, add a refresh-token flow + per-user `token_version` bumped on logout-all-devices. Thesis prototype doesn't need this.

### Role / permission system

**None.** Authenticated endpoints check "is this the user's resource?" where applicable (e.g. `GET /chat/{sid}/history` returns 404 if not owner — leak-safe). Guest vs registered differ only in the token's `is_guest` claim and in the user doc; no behavioral gating today.

### Public vs protected routes

| Public (no auth) | Protected (JWT required) |
|---|---|
| `GET /health` | `GET /users/me` |
| `POST /auth/register` | `POST /users/onboarding` |
| `POST /auth/login` | `GET /recommendations/dashboard` |
| `POST /auth/guest` | `POST /chat`, `GET /chat/{sid}/history` |
| `GET /sensors` | `POST /devices/register-push-token` |
| `GET /aqi/current`, `GET /aqi/sensors` ¹ | `DELETE /devices/push-token` |
| `GET /predictions` ¹ | `GET /notifications`, `PATCH /notifications/{id}/read` |
| `GET /analytics/*` ¹ | `GET /notifications/settings`, `PATCH /notifications/settings` |
| `GET /docs`, `/redoc`, `/openapi.json` | |

¹ Currently unauthenticated — these aqi/predictions/analytics endpoints don't apply `Depends(get_current_user_id)`. Not a thesis problem; add the dependency if you want to gate them.

---

## 6. API Routes — COMPLETE LIST

Base URL during dev: `http://localhost:8080`. All non-public endpoints take JWT via `Authorization: Bearer <token>`.

### Health

#### `GET /health`
- **Auth**: no. **Response 200**: `{"status": "healthy"}`.

### Auth (`/auth`)

#### `POST /auth/register`
- **Auth**: no.
- **Body**: `{ email: str, password: str (min 6), name?: str }`.
- **Response 200**: `{ access_token, token_type: "bearer", user: UserOut }`.
- **Errors**: 409 (email exists), 422 (validation).

#### `POST /auth/login`
- **Auth**: no.
- **Body**: `{ email, password }`.
- **Response 200**: same shape.
- **Errors**: 401 (invalid email/password — message identical to avoid enumeration).

#### `POST /auth/guest`
- **Auth**: no.
- **Body**: `{ device_id?: str }`.
- **Response 200**: same shape; `user.is_guest=true`, `user_id` prefix `guest_`.

### Users (`/users`)

#### `GET /users/me`
- **Auth**: YES.
- **Response 200**: `MeResponse { user_id, email?, name?, is_guest, vulnerability_category, vulnerability_score?, onboarding_completed, profile?, profile_last_updated? }`.
- **Errors**: 401, 404 (token's user not in DB).

#### `POST /users/onboarding`
- **Auth**: YES. Works for both guest and registered users.
- **Body**: `UserOnboardingRequest` (name?, age, gender?, chronic_diseases, asthma, cardiovascular, allergies, smoking_status, activity_level, pollution_sensitivity, preferred_locations, is_pregnant?, outdoor_worker?, intense_sport?, low_socioeconomic?).
- **Response 200**: `{ user_id, vulnerability_category, vulnerability_score, contributing_factors: [str], profile_last_updated }`. Does NOT echo the profile back.
- **Side effects**: updates the user doc; subsequent recommendation/alert cycles use the new category.

### Sensors (`/sensors`)

#### `GET /sensors`
- **Auth**: no.
- **Response 200**: `{ count, sensors: [{ sensor_id, latitude, longitude, sensor_radius_km?, last_seen? }] }`. Mobile uses this for nearest-sensor lookup.

### AQI (`/aqi`)

Both endpoints JOIN `aqi_results` with the latest `sensor_readings` doc.

#### `GET /aqi/current?sensor_id=X`
- **Auth**: no.
- **Response 200**:
```json
{
  "sensor_id": "...", "timestamp": "...",
  "aqi_score": 75, "aqi_category": "Moderate",
  "risk_level": "moderate", "dominant_pollutant": "PM25",
  "sub_indices": { "PM25": 75, ... },
  "latitude": 36.75, "longitude": 3.04, "sensor_radius_km": 2.5,
  "pollutants": { "PM25": 22.0, ... },
  "weather": { "temperature_2m": 22, "relative_humidity_2m": 65,
               "wind_speed_10m": 11, "wind_direction_10m": 240 }
}
```
- **Errors**: 404 (no AQI yet for that sensor).

#### `GET /aqi/sensors`
- **Auth**: no.
- **Response 200**: `{ count, sensors: [AQIResultResponse] }` — same enriched shape, one entry per sensor.

### Predictions (`/predictions`)

#### `GET /predictions?sensor_id=X`
- **Auth**: no.
- **Response 200**: `{ sensor_id, generated_at, forecast_horizon_hours: 12, predictions: [12 entries] }`.
- **Errors**: 404 (no forecast yet).

### Recommendations (`/recommendations`)

#### `GET /recommendations/dashboard?sensor_id=Y`
- **Auth**: YES.
- **Response 200**: `DashboardRecommendationResponse` (sensor_id, vulnerability_category, generated_at, forecast_aqi_max, forecast_category, rule_output, recommendation_text).
- **Errors**: 401, 404 (no reco for combo), 409 (user has no vulnerability_category — onboarding not done).

### Analytics (`/analytics`)

All three are read-only DuckDB queries against the Parquet lakehouse. AQI is computed inline by `aqi_service` (not read from `aqi_results`).

#### `GET /analytics/trend?sensor_id=X&hours=48`
- **Auth**: no.
- **Response 200**: `{ sensor_id, range, points: [{timestamp, aqi}], avg_aqi, peak_aqi, worst_day }`. Empty `points` if no data.

#### `GET /analytics/worst-day?days=7`
- **Auth**: no.
- **Response 200**: `{ days, worst_day, worst_day_date, worst_day_aqi, worst_day_category, daily_summary: [{date, day_name, avg_aqi, aqi_category}] }`.

#### `GET /analytics/sensor-comparison?hours=24`
- **Auth**: no.
- **Response 200**: `{ range, sensors: [{sensor_id, avg_aqi, aqi_category, n_samples}] }`, sorted worst-first.

### Chat (`/chat`)

#### `POST /chat`
- **Auth**: YES.
- **Body**: `{ session_id?: str, message: str }`.
- **Response 200**: `{ session_id, agent_used, response }`.
  - `agent_used` examples: `"Knowledge"`, `"Analytics"`, `"PersonalAdvisor"`, `"PersonalAdvisor,Analytics"`, `"team"` (fallback), `"error"`.
- **Side effects**: persists user + assistant messages in `chat_sessions`.

#### `GET /chat/{session_id}/history`
- **Auth**: YES; returns 404 if session does not belong to caller (leak-safe).
- **Response 200**: `{ session_id, user_id, created_at, updated_at, message_count, messages: [{role, content, timestamp, agent_used}] }`.

### Devices (`/devices`)

#### `POST /devices/register-push-token`
- **Auth**: YES.
- **Body**: `{ expo_push_token, platform, device_id?, app_version? }` (user_id from JWT).
- **Response 200**: `{ success: true }`. Upserts the token; sets `active=true`.

#### `DELETE /devices/push-token`
- **Auth**: YES.
- **Body**: `{ expo_push_token }`.
- **Response 200**: `{ success: true }`. Sets `active=false`.
- **Errors**: 404 (token not found for this user).

### Notifications (`/notifications`)

#### `GET /notifications?limit=50&only_unread=false`
- **Auth**: YES.
- **Response 200**: `{ count, unread_count, notifications: [NotificationResponse] }`.

#### `PATCH /notifications/{notification_id}/read`
- **Auth**: YES. **Response 200**: `{ success: true }`. **Errors**: 404 (not found or not owned).

#### `GET /notifications/settings`
- **Auth**: YES. **Response 200**: `NotificationSettings` with defaults merged in.

#### `PATCH /notifications/settings`
- **Auth**: YES.
- **Body**: `NotificationSettingsUpdate` (any subset of fields).
- **Response 200**: updated `NotificationSettings`.

---

## 7. Business Logic & Services

### `services/aqi_service.py`
US EPA AQI breakpoint tables (PM2.5 with 2024 NAAQS revision), unit conversion (µg/m³ → ppb/ppm), truncation per EPA handbook.
- Exports: `compute_sub_index(pollutant, value_ugm3)`, `compute_overall_aqi(sub_indices)`, `get_aqi_category(aqi)`, `get_risk_level(category)`, `compute_aqi_from_pollutants(pollutants_dict)`, `build_aqi_result(SensorEvent)`.
- Used by: `aqi_consumer`, `forecast_scheduler`, `lakehouse/query_engine`, `recommendation_engine`.

### `services/forecast_service.py`
HTTP client for the Mamba forecast model. Exports `fetch_sensor_history`, `build_mamba_payload`, `call_mamba_api`, `parse_forecast_response`, plus errors `ForecastError`, `InsufficientHistoryError`, and models `PredictionDocument`, `ForecastedHour`.

### `services/recommendation_engine.py`
- **Constants**: `VULNERABILITY_CATEGORIES` (`générale`/`sensible`/`vulnérable`), `THRESHOLDS_BY_CATEGORY` (per-pollutant caution/avoid/danger in µg/m³), `POLLUTANT_RISKS`, urgency levels.
- **Vulnerability**: `compute_vulnerability_category(profile) → (category, score, factors)`. Score from age, asthma, cardiovascular, chronic_diseases, pregnancy, smoking, activity, sensitivity, outdoor worker.
- **Rule engine (Layer A)**: `compute_rule_based_recommendation(category, forecast_predictions) → RuleRecommendationResult`. Computes AQI trajectory, per-pollutant scores, flagged pollutants, urgency, key risks.
- **LLM layer (Layer B)**: `generate_recommendation_text(rule)` — calls `services.llm_client.call_chat_llm`; falls back to a deterministic French template on LLM failure.
- **Smart regen**: `should_regenerate_recommendation(previous_doc, new_rule, regen_interval_hours, now) → (bool, reason)`.

### `services/alert_dispatcher.py`
`dispatch_alerts_for_cycle(transitions, now)` — called by the recommendation_scheduler at end of cycle.
- Filters transitions where urgency escalated past `ALERT_URGENCY_THRESHOLD`.
- Loads sensor coordinates once and users-per-category once.
- Per user: nearest-sensor check (haversine), opt-in check, quiet-hours check (bypassed for `danger`), cooldown check (queries `notifications` collection).
- Records the notification BEFORE attempting Expo push (in-app center works even without registered tokens).

### `services/llm_client.py`
`call_chat_llm(system, user, history?, max_tokens=250, temperature=0.3)` — OpenAI-compat chat completion. Provider determined by `LLM_API_BASE_URL`. Errors: `LLMUnavailableError`, `LLMError`.

### `services/push_client.py`
`send_push(tokens, title, body, data, priority, sound, channel_id)` — Expo Push v2. Errors: `PushUnavailableError`, `PushError`.

### `services/auth_service.py`
`hash_password`, `verify_password` — direct bcrypt (not passlib). `create_access_token(sub, is_guest, expires_minutes?)`, `decode_access_token(token)`. Error: `InvalidTokenError`.

### Complex workflows

**Recommendation + alert cycle** (every `RECOMMENDATION_SCHEDULER_INTERVAL_SECONDS`):
```
for each sensor with predictions:
  for each vulnerability_category:
    new_rule = compute_rule_based_recommendation(category, predictions)
    previous = dashboard_recommendations.find_one(...)
    if should_regenerate_recommendation(previous, new_rule):
      text = generate_recommendation_text(new_rule)   # LLM (with fallback)
    else:
      text = previous.recommendation_text              # reuse
    queue upsert of dashboard_recommendations
    collect (sensor_id, category, previous, new_rule) for the dispatcher

bulk_write all upserts
dispatch_alerts_for_cycle(transitions):
  filter alertable (urgency escalated past threshold)
  load sensor coordinates once
  for each affected category:
    load users in that category once
    for each user whose nearest sensor matches:
      check opt-in / quiet hours / cooldown
      record notification + (try to) push via Expo
```

**Chatbot turn** (`POST /chat`):
```
orchestrator.handle_message(user_id, session_id, message):
  session_id = session_id or create_session(user_id)
  history = get_recent_history(session_id, CHAT_HISTORY_WINDOW)
  sensor_id = resolve_user_sensor(user_id)
  current_aqi = get_current_air_quality(sensor_id)        # pre-fetched
  team = build_team(user_id, sensor_id, session_id, history, current_aqi)
  result = await team.arun(message)                        # Agno coordinate mode
  agents_used = extract from result.member_responses
  append both messages to chat_sessions
  return { session_id, agent_used, response }
```

### Background jobs / scheduled tasks

| Process | Cadence | Trigger |
|---|---|---|
| `producer` | every `SIMULATION_TICK_SECONDS` (5s) | Internal asyncio loop |
| `raw_writer_consumer` | continuous | Kafka `getmany` loop |
| `aqi_consumer` | continuous | Kafka `getmany` loop |
| `lakehouse_writer` | continuous; flush on 200 records OR 30 s | Kafka `getmany` + buffer |
| `forecast_scheduler` | every 5 s | Standalone OR APScheduler in FastAPI |
| `recommendation_scheduler` | every 15 s | Standalone OR APScheduler in FastAPI |
| `alert_dispatcher` | called from recommendation cycle | Not standalone |

When `ENABLE_IN_PROCESS_SCHEDULER=true`, forecast + recommendation run inside FastAPI via `schedulers/in_process.py` (AsyncIOScheduler).

---

## 8. Error Handling

### Global handler

`api/main.py` registers a catch-all `@app.exception_handler(Exception)`:
- Logs the full traceback via `logger.exception(...)` to the uvicorn terminal.
- Returns `{"detail": "Internal server error"}` with status 500.
- **Never leaks stack traces to the client.**

FastAPI's own `HTTPException` handler stays — those produce proper `{"detail": "..."}` bodies with the right status.

### Custom error classes

| Class | Module | When raised |
|---|---|---|
| `AQIComputationError` | `services/aqi_service.py` | invalid pollutant values |
| `ForecastError`, `InsufficientHistoryError` | `services/forecast_service.py` | Mamba HTTP failure, missing 168-row window |
| `RecommendationError` | `services/recommendation_engine.py` | unknown category, no predictions |
| `LLMError`, `LLMUnavailableError` | `services/llm_client.py` | non-200 or network failure |
| `PushError`, `PushUnavailableError` | `services/push_client.py` | Expo failure |
| `InvalidTokenError` | `services/auth_service.py` | JWT bad/expired |

### Client-facing error codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 401 | Missing or invalid JWT |
| 404 | Resource not found OR not owned (chat history) — leak-safe |
| 409 | Conflict (email exists, user has no vulnerability_category yet) |
| 422 | Pydantic validation failure |
| 500 | Server error (traceback in logs; generic message to client) |

### Consumer / scheduler resilience

- Per-message: validation + computation errors are logged and skipped; loop never crashes.
- Per cycle: top-level `try/except Exception` keeps the loop alive.
- Mongo bulk writes use `ordered=False`; `BulkWriteError` caught; duplicate-key errors (11000) silently tolerated.

---

## 9. Middleware

### Global

1. **`CORSMiddleware`** — permissive (`allow_origins=["*"]`). Tighten in production.
2. **Global exception handler** (see §8).
3. **JWT bearer scheme** — registered as `HTTPBearer(auto_error=False)` and applied per route via `Depends(get_current_user_id)`. Not a true middleware.

### Route-level dependencies

- Auth: `get_current_user_id` (required) or `get_current_user_id_optional` on every protected route.
- DB: every router uses `Depends(get_<collection>_collection)` instead of importing Motor accessors directly. Lives in `api/dependencies.py`.

### No third-party middleware

No rate limiting, no observability tracing, no request logging beyond uvicorn defaults. Thesis prototype.

---

## 10. File / Storage Handling

### CSV input

`data/raw_csv/` — one (or many) CSV files. Required columns: `sensor_id, center_latitude, center_longitude, sensor_radius_km, time, pm10, pm2_5, nitrogen_dioxide, ozone, carbon_monoxide, sulphur_dioxide, temperature_2m, relative_humidity_2m, wind_speed_10m, wind_direction_10m`. The producer concatenates all `.csv` files and renames columns via `CSV_COLUMN_MAP` in `streaming/producer.py`.

### Parquet lakehouse

`data/lakehouse/date=YYYY-MM-DD/batch_<uuid12>.parquet`. Written by `consumers/lakehouse_writer.py` via `lakehouse/writer.py`. Read by `lakehouse/query_engine.py` via DuckDB `read_parquet(..., hive_partitioning=1)`.

### KB PDFs

`data/kb_pdfs/` (suggested). Run `python -m chatbot.ingest_pdfs data/kb_pdfs`. Chunked into ~300-word windows with 40-word overlap. Embeddings computed at ingest time, stored in `knowledge_chunks.embedding`.

### No object storage

No S3 / GridFS / etc. All persistent files are on the local filesystem and bind-mounted into the relevant containers via `docker-compose.yml`.

---

## 11. Testing

### Status

**No automated tests written.** Step 13 of the plan (tests + production polish) was deferred — each step was verified manually via PowerShell + Swagger UI.

### Suggested layout when added

```
tests/
├── test_aqi_service.py            # pure-function unit tests
├── test_recommendation_engine.py  # rule engine with synthetic forecasts
├── test_lakehouse_query.py        # DuckDB on fixture Parquet
├── test_api_aqi.py                # FastAPI TestClient + mongomock-motor
└── conftest.py                    # shared fixtures
```
Add a `requirements-dev.txt` with: `pytest`, `pytest-asyncio`, `mongomock-motor`, `httpx` (already pinned in main).

---

## 12. Known Issues / TODOs

### Code-level

1. **`JWT_SECRET_KEY` default is `"change-me-in-production"`.** Must be replaced before any non-thesis use.
2. **No refresh-token flow.** When a JWT expires, the client must re-login (or re-create a guest). With 7-day registered tokens and 30-day guest tokens, acceptable for a thesis demo.
3. **`/aqi/*`, `/predictions`, `/sensors`, `/analytics/*` are unauthenticated.** Add `Depends(get_current_user_id_optional)` if you want to gate or log.
4. **Cooldown is per `(user, sensor)`**: a `danger` alert may be suppressed if an `avoid` alert was sent for the same pair within the cooldown window. If `danger` should bypass cooldown, edit `_try_send_user_alert` in `services/alert_dispatcher.py`.
5. **Only `fr` and `en` notification templates** exist (`services/alert_dispatcher._TEMPLATES`). Adding a language = adding a dict.
6. **Local cosine retrieval is O(n)** — fine for ≤10k chunks. For larger KBs, set `USE_ATLAS_VECTOR_SEARCH=true` and create the Atlas index.
7. **No metrics / observability** (no Prometheus exporter, no request timing).
8. **Chatbot `agent_used` extraction is best-effort** — Agno's API has shifted across 1.x versions. If `member_responses` isn't surfaced in your installed version, the field falls back to `"team"` (functional but loses per-agent visibility).

### Operational

1. **Mamba external; port collision.** Real Mamba on `:8000`, `mock_mamba.py` also on `:8000`. **FastAPI deliberately uses `:8080`** to avoid the conflict.
2. **`.env` lives in `backend/`** (not `backend/docker/`) so host-side processes can pick it up. The template lives in `backend/docker/.env.example`.
3. **bcrypt 4.x + passlib incompatibility** — fixed by calling bcrypt directly. `passlib` is still in `requirements.txt` (pulled transitively) but unused by our code.
4. **Atlas vector index must be created manually** in the Atlas UI. `ensure_knowledge_chunks_indexes` only creates the BTREE indexes.
5. **OneDrive path** — the project lives under `OneDrive` which can occasionally cause file-lock weirdness with Docker volume mounts on Windows.

### Frontend integration gaps (referenced by `thesis_frontend_context_v4.txt`)

1. **No `POST /users/update_profile`** — `POST /users/onboarding` is an upsert and doubles as the update endpoint.
2. **No `POST /auth/upgrade`** (guest → registered with data carry-over). Out of scope.

---

## 13. Continuation Notes

### Where we stopped

**Step 12 is complete.** Final substantive changes:
- `api/routers/aqi.py` — `/aqi/current` and `/aqi/sensors` now JOIN `sensor_readings` and expose `latitude`, `longitude`, `sensor_radius_km`, `pollutants` (raw µg/m³), and `weather`. Closes the biggest frontend gap from v4.
- `schedulers/in_process.py` — APScheduler-driven forecast + recommendation jobs that run inside FastAPI when `ENABLE_IN_PROCESS_SCHEDULER=true`. Standalone runners still work.
- `chatbot/ingest_pdfs.py` — CLI to convert a directory of PDFs into `knowledge_chunks` (pypdf + sentence-transformers).
- `requirements.txt` — added `pypdf>=4.0.0`; pinned `bcrypt>=4.0,<5.0` explicitly.

### Open thread to verify on the next session

**Step 11's `POST /auth/register`** showed a generic 500 (`{"detail":"Internal server error"}`) twice for the user. The likely cause (passlib + bcrypt 4.1) was fixed in `services/auth_service.py` by switching to direct bcrypt. The user has not yet confirmed the fix end-to-end — the actual traceback never made it into the conversation. **First thing to do next session**: full uvicorn restart (Ctrl+C + re-run, not `--reload`) and re-test register. If still failing, the uvicorn terminal traceback is the entry point.

### Suggested next steps (priority order)

1. **Verify the auth fix end-to-end.** Confirm `pip show bcrypt` reports `4.x`; full uvicorn restart; re-test `POST /auth/register`.
2. **Step 13 — tests + production polish.** Start with pure-function unit tests for `aqi_service` and `recommendation_engine` — high value, no infrastructure dependencies.
3. **Tighten unauthenticated endpoints** if thesis defense will probe security.
4. **Frontend integration support** — point the React Native app at the now-stable API. The v4 frontend brief (`thesis_frontend_context_v4.txt`) is already aligned to actual response shapes.
5. **Final demo script** — a single PowerShell that brings up the full stack + runs the demo REST calls in order, suitable for the defense.

### Deliberately NOT done

- No tests, no CI.
- No refresh tokens.
- No rate limiting.
- No request tracing / metrics.
- No HTTPS / TLS (uvicorn HTTP only).
- No production Dockerfile — same `Dockerfile.api` is used for dev and every container.

### Sanity-check checklist for "is the backend still healthy?"

```powershell
# 1. Infra up?
cd C:\Users\kizmo\OneDrive\Desktop\school\PFE\Air_quality_recommendation\backend\docker
docker compose ps           # all healthy

# 2. Mongo reachable?
docker compose exec mongo mongosh --quiet --eval "db.adminCommand('ping').ok"

# 3. Sensor stream flowing?
docker compose exec mongo mongosh airquality --quiet --eval "db.sensor_readings.countDocuments({})"

# 4. AQI computing?
docker compose exec mongo mongosh airquality --quiet --eval "db.aqi_results.countDocuments({})"

# 5. Forecasts coming back?
docker compose exec mongo mongosh airquality --quiet --eval "db.predictions.countDocuments({})"

# 6. Recommendations regenerating?
docker compose exec mongo mongosh airquality --quiet --eval "db.dashboard_recommendations.findOne({}, {generated_at:1, _id:0})"

# 7. API up?
Invoke-RestMethod http://localhost:8080/health

# 8. End-to-end via Swagger
Start-Process http://localhost:8080/docs
```

If any step fails, that's the entry point for debugging.

---

**End of handoff document.**
