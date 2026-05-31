"""
Chat router — multi-agent RAG chatbot with session memory.

POST /chat                     — orchestrator handles the message
GET  /chat/{session_id}/history — full conversation transcript
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_current_user_id
from chatbot.orchestrator import handle_message
from chatbot.session_manager import get_session
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = Field(
        default=None,
        description="Existing session id; omit to start a new conversation.",
    )
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    agent_used: str
    response: str


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    timestamp: datetime
    agent_used: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    messages: List[ChatMessageResponse]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the multi-agent chatbot",
)
async def post_chat(
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
) -> ChatResponse:
    result = await handle_message(
        user_id=user_id,
        session_id=body.session_id,
        message=body.message,
    )
    return ChatResponse(**result)


@router.get(
    "/{session_id}/history",
    response_model=ChatHistoryResponse,
    summary="Retrieve a chat session's full message history",
)
async def get_history(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
) -> ChatHistoryResponse:
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if session.user_id != user_id:
        # Don't leak the existence of someone else's session.
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return ChatHistoryResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(session.messages),
        messages=[
            ChatMessageResponse(**m.model_dump()) for m in session.messages
        ],
    )
