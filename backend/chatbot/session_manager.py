"""
Chat session memory backed by MongoDB `chat_sessions`.

Document shape:
{
  session_id: str,
  user_id: str,
  created_at: datetime,
  updated_at: datetime,
  messages: [
    { role, content, timestamp, agent_used }
  ]
}

Storage is mostly unbounded (capped by CHAT_MAX_MESSAGES_PER_SESSION via
$slice on push). The LLM only receives the last CHAT_HISTORY_WINDOW
messages — see `get_recent_history`.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from core.config import settings
from core.logger import get_logger
from core.mongo_client import chat_sessions

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime
    agent_used: Optional[str] = None


class ChatSession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_session(user_id: str) -> str:
    """Create a new empty session. Returns the new session_id."""
    session_id = str(uuid.uuid4())
    now = _utc_now_naive()
    await chat_sessions().insert_one(
        {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
    )
    logger.info("Chat session created session_id=%s user_id=%s", session_id, user_id)
    return session_id


async def get_session(session_id: str) -> Optional[ChatSession]:
    """Fetch the full session (all messages)."""
    doc = await chat_sessions().find_one(
        {"session_id": session_id}, projection={"_id": 0}
    )
    if not doc:
        return None
    return ChatSession(**doc)


async def get_recent_history(session_id: str, n: int) -> List[ChatMessage]:
    """Fetch only the last N messages of a session (LLM context window)."""
    doc = await chat_sessions().find_one(
        {"session_id": session_id},
        projection={"_id": 0, "messages": {"$slice": -n}},
    )
    if not doc or not doc.get("messages"):
        return []
    return [ChatMessage(**m) for m in doc["messages"]]


async def append_message(
    session_id: str,
    *,
    role: str,
    content: str,
    agent_used: Optional[str] = None,
) -> None:
    """Append one message and bump updated_at. Caps messages via $slice."""
    msg = {
        "role": role,
        "content": content,
        "timestamp": _utc_now_naive(),
        "agent_used": agent_used,
    }
    await chat_sessions().update_one(
        {"session_id": session_id},
        {
            "$push": {
                "messages": {
                    "$each": [msg],
                    # Keep only the most recent N messages (storage cap).
                    "$slice": -settings.CHAT_MAX_MESSAGES_PER_SESSION,
                }
            },
            "$set": {"updated_at": msg["timestamp"]},
        },
    )


def history_to_llm_messages(history: List[ChatMessage]) -> List[dict]:
    """Convert ChatMessage list → OpenAI chat-completion `messages` shape."""
    return [{"role": m.role, "content": m.content} for m in history]
