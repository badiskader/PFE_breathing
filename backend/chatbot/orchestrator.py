"""
Chat orchestrator (Agno-backed).

Thin layer around the Agno `Team`:

  1. Ensure / load session.
  2. Resolve the user's nearest sensor (shared by every agent).
  3. Pre-fetch the current AQI snapshot ONCE (avoids redundant tool calls
     by individual agents).
  4. Build the Team with per-session context.
  5. Run `team.arun(message)`.
  6. Persist the user message + assistant reply (with which agents fired).

The public function signature `handle_message(user_id, session_id, message)`
is unchanged from the previous implementation, so `api/routers/chat.py`
keeps working as-is.
"""

from typing import List, Optional

from chatbot.context import (
    format_aqi_snapshot,
    format_history_for_context,
    resolve_user_sensor,
)
from chatbot.session_manager import (
    ChatMessage,
    append_message,
    create_session,
    get_recent_history,
)
from chatbot.team import build_team
from chatbot.tools import get_current_air_quality
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def _extract_agents_used(response) -> str:
    """Best-effort extraction of which member agents fired during the run.

    Agno's RunResponse object exposes member outputs under one of a few
    attribute names depending on version. We try the common ones and fall
    back to a generic 'team' label so we always store SOMETHING in the
    chat_sessions document.
    """
    try:
        members = (
            getattr(response, "member_responses", None)
            or getattr(response, "members_responses", None)
            or []
        )
        names: List[str] = []
        for r in members:
            n = (
                getattr(r, "agent_id", None)
                or getattr(r, "agent_name", None)
                or getattr(r, "name", None)
            )
            if n:
                names.append(str(n))
        if names:
            # Preserve order, dedupe.
            return ",".join(dict.fromkeys(names))
    except Exception as e:
        logger.debug("could not extract agents_used: %s", e)
    return "team"


async def handle_message(
    user_id: str,
    session_id: Optional[str],
    message: str,
) -> dict:
    """Process one chat turn end-to-end.

    Returns:
        { "session_id", "agent_used", "response" }
    """
    # 1. Ensure session.
    if not session_id:
        session_id = await create_session(user_id)
        history: List[ChatMessage] = []
    else:
        history = await get_recent_history(session_id, settings.CHAT_HISTORY_WINDOW)

    # 2. Resolve sensor.
    sensor_id = await resolve_user_sensor(user_id) or "UNKNOWN"
    if sensor_id == "UNKNOWN":
        logger.warning("No sensor could be resolved for user_id=%s", user_id)

    # 3. Pre-fetch current AQI ONCE so all agents share the same snapshot.
    current_aqi: dict = {}
    if sensor_id != "UNKNOWN":
        try:
            current_aqi = await get_current_air_quality(sensor_id)
        except Exception as e:
            logger.warning("Pre-fetch of current AQI failed: %s", e)
            current_aqi = {}

    # 4. Build team with per-session context.
    aqi_block = format_aqi_snapshot(current_aqi)
    history_block = format_history_for_context(history)
    team = build_team(
        user_id=user_id,
        sensor_id=sensor_id,
        session_id=session_id,
        aqi_block=aqi_block,
        history_block=history_block,
    )

    # 5. Run the team — never crash the API on agent failure.
    try:
        result = await team.arun(message)
        response_text = (getattr(result, "content", None) or str(result)).strip()
        agents_used = _extract_agents_used(result)
    except Exception as e:
        logger.exception(
            "Team run failed for session=%s user=%s: %s", session_id, user_id, e
        )
        response_text = "Désolé, une erreur s'est produite. Veuillez réessayer."
        agents_used = "error"

    logger.info(
        "Chat turn | session=%s user=%s sensor=%s agents=%s msg=%r",
        session_id, user_id, sensor_id, agents_used, message[:80],
    )

    # 6. Persist both turns.
    await append_message(session_id, role="user", content=message)
    await append_message(
        session_id, role="assistant", content=response_text, agent_used=agents_used
    )

    return {
        "session_id": session_id,
        "agent_used": agents_used,
        "response": response_text,
    }
