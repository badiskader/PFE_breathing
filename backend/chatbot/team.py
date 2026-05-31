"""
Agno-powered multi-agent team.

Three specialist agents wrapped in an Agno `Team` running in `coordinate`
mode — the team leader (an LLM) decides which member(s) handle each
message and synthesizes the final reply. For compound questions, several
specialists can run in parallel and their outputs are merged.

This replaces the previous hand-rolled keyword-routing orchestrator.

Agents
------
  PersonalAdvisor  Personalized health advice based on the user's profile.
  Analytics        Forecasts, historical trends, temporal questions.
  Knowledge        General air-quality science Q&A, grounded by RAG.

Shared context injected into every agent:
  - user_id, sensor_id, session_id (so tools receive the right arguments)
  - current AQI snapshot (pre-fetched once per turn, saves repeat calls)
  - recent conversation history
"""

from agno.agent import Agent
from agno.models.groq import Groq
from agno.team import Team

from chatbot.tools import (
    compute_statistics,
    get_conversation_history,
    get_current_air_quality,
    get_forecast,
    get_historical_data,
    get_user_profile,
    query_knowledge_base,
)
from core.config import settings


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def _model() -> Groq:
    """Build a Groq model bound to our configured key + model id."""
    return Groq(id=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)


# ---------------------------------------------------------------------------
# Instruction blocks
# ---------------------------------------------------------------------------

_PERSONAL_ADVISOR_INSTRUCTIONS = """\
You are a PERSONALIZED air-quality HEALTH advisor.

REQUIRED WORKFLOW:
1. Call `get_user_profile(user_id)` FIRST to load the user's health
   profile — age, asthma, cardiovascular issues, chronic_diseases,
   smoking_status, allergies, activity_level, pollution_sensitivity, etc.
2. Use the CURRENT AQI SNAPSHOT provided in the SESSION CONTEXT block
   (already pre-fetched). Only call `get_current_air_quality` if you need
   to refresh it or if SESSION CONTEXT shows no snapshot.
3. If a medical concept needs grounding (e.g. "ozone effect on asthma"),
   call `query_knowledge_base`.
4. If the user references earlier in the conversation and the recent
   history isn't enough, call `get_conversation_history` for more turns.

OUTPUT RULES:
- 3 to 5 sentences. Prefer French phrasing.
- Reference the user's SPECIFIC conditions (e.g. "compte tenu de votre
  asthme…") and give CONCRETE actions (timing, mask, indoor vs outdoor).
- NEVER invent profile fields.
- Do NOT mention raw AQI numbers — use categories instead (Good /
  Moderate / Unhealthy for Sensitive Groups / Unhealthy / Very
  Unhealthy / Hazardous).
- If `get_user_profile` returns an error, politely ask the user to
  complete onboarding before giving personalized advice.
"""

_ANALYTICS_INSTRUCTIONS = """\
You are the analytics & forecasting agent.

REQUIRED WORKFLOW:
1. For FUTURE questions ("tomorrow", "this afternoon", "next 6 hours"):
   call `get_forecast(sensor_id)` — optionally with `target_datetime`.
2. CRITICAL FALLBACK BEHAVIOR — if `get_forecast` returns
   `{"available": false, ...}`:
     a. DO NOT respond with "I don't know" or "no data available".
     b. Determine the relevant hour-of-day window from the user's question
        (e.g. "this afternoon" → start_hour=14, end_hour=18; "tomorrow
        morning" → start_hour=6, end_hour=10).
     c. Call `get_historical_data(sensor_id, start_hour=…, end_hour=…,
        day_of_week=…)` to retrieve the typical AQI pattern.
     d. Reply along the lines of: "D'après les tendances historiques,
        l'AQI ici autour de <heure> se situe en moyenne autour de <avg>
        (entre <min> et <max>). La prévision réelle d'aujourd'hui sera
        disponible plus tard."
3. For trends / comparisons / peaks: use `get_historical_data` (with
   filters) and optionally `compute_statistics`.

OUTPUT RULES:
- 2 to 4 sentences. Factual tone. Prefer French.
- NEVER invent numbers — only quote values present in tool returns.
- When using historical fallback, make clear it's historical, not a
  forecast.
- Don't suggest for the user to go check another website or app for the forecast
"""

_KNOWLEDGE_INSTRUCTIONS = """\
You are the air-quality KNOWLEDGE agent.

REQUIRED WORKFLOW:
1. ALWAYS call `query_knowledge_base(query)` first.
2. Answer ONLY from the retrieved chunks. If the chunks don't cover the
   question, say so explicitly — do NOT invent.
3. When the question is abstract but local conditions would help
   ("Is ozone bad right now?"), also use the CURRENT AQI SNAPSHOT from
   SESSION CONTEXT to add a one-line concrete tie-in.

OUTPUT RULES:
- 2 to 4 sentences.
- Cite sources inline as [source].
- Prefer French.
"""

_TEAM_INSTRUCTIONS = """\
You coordinate three air-quality specialists:

  • PersonalAdvisor: personal HEALTH advice tailored to the user's profile.
  • Analytics:       forecasts, historical patterns, comparisons, trends.
  • Knowledge:       general air-quality facts and science, grounded by RAG.

ROUTING RULES:
1. Personal / "should I" / "for me" / "my asthma" → PersonalAdvisor.
2. Time-bound, forecast, trend, comparison, average, "yesterday",
   "tomorrow", "this afternoon" → Analytics.
3. Definitions / mechanisms / "what is" / "why" / "WHO threshold" →
   Knowledge.
4. COMPOUND questions (e.g. "is tomorrow afternoon safe for my asthmatic
   kid?") → delegate to MULTIPLE specialists in parallel, then MERGE
   their outputs into a single coherent reply.

When merging, never repeat the same fact twice. The FINAL ANSWER must be
ONE cohesive 2-to-5-sentence reply. If the user wrote in French, reply
in French.

Always pass the user_id, sensor_id, and session_id from the SESSION
CONTEXT block to the specialists — DO NOT invent identifiers.
"""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def build_session_context(
    *,
    user_id: str,
    sensor_id: str,
    session_id: str,
    aqi_block: str = "",
    history_block: str = "",
) -> str:
    """Render the SESSION CONTEXT block injected into every agent and the team leader."""
    parts = [
        "SESSION CONTEXT:",
        f"  user_id     = {user_id}",
        f"  sensor_id   = {sensor_id}    # use this for all sensor/location tool calls",
        f"  session_id  = {session_id}",
        "When a tool needs user_id, sensor_id, or session_id, pass these EXACT values.",
    ]
    if aqi_block:
        parts.append("")
        parts.append(aqi_block)
    if history_block:
        parts.append("")
        parts.append(history_block)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Team builder
# ---------------------------------------------------------------------------

def build_team(
    *,
    user_id: str,
    sensor_id: str,
    session_id: str,
    aqi_block: str = "",
    history_block: str = "",
) -> Team:
    """Construct the Agno team with per-session context wired into each member."""

    shared_context = build_session_context(
        user_id=user_id,
        sensor_id=sensor_id,
        session_id=session_id,
        aqi_block=aqi_block,
        history_block=history_block,
    )

    personal_advisor = Agent(
        name="PersonalAdvisor",
        role="Personalized air-quality health advice based on the user's profile.",
        model=_model(),
        tools=[
            get_user_profile,
            get_current_air_quality,
            get_conversation_history,
            query_knowledge_base,
        ],
        instructions=_PERSONAL_ADVISOR_INSTRUCTIONS,
        additional_context=shared_context,
    )

    analytics = Agent(
        name="Analytics",
        role="Forecasts, historical trends, and temporal analytical questions.",
        model=_model(),
        tools=[
            get_forecast,
            get_historical_data,
            get_current_air_quality,
            compute_statistics,
        ],
        instructions=_ANALYTICS_INSTRUCTIONS,
        additional_context=shared_context,
    )

    knowledge = Agent(
        name="Knowledge",
        role="General air-quality, pollutant, and health-science Q&A grounded by RAG.",
        model=_model(),
        tools=[
            query_knowledge_base,
            get_current_air_quality,
        ],
        instructions=_KNOWLEDGE_INSTRUCTIONS,
        additional_context=shared_context,
    )

    return Team(
        name="AirQualityTeam",
        mode="coordinate",
        model=_model(),
        members=[personal_advisor, analytics, knowledge],
        instructions=_TEAM_INSTRUCTIONS,
        additional_context=shared_context,
    )
