"""
Shared LLM client.

Single chokepoint for every chat-completion call in the system:
  - recommendation_engine (Type 1 dashboard text)
  - chatbot agents (Type 2 personalized + knowledge/analytics/health)

Provider-agnostic: works with any OpenAI-compatible chat-completion API
(Groq, OpenAI, Ollama with /v1). Swap by setting `LLM_API_BASE_URL`.
"""

from typing import Dict, List, Optional

import httpx

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class LLMUnavailableError(Exception):
    """The LLM provider is unreachable or unconfigured (caller may fall back)."""


class LLMError(Exception):
    """The LLM returned an unexpected response."""


async def call_chat_llm(
    system: str,
    user: str,
    *,
    history: Optional[List[Dict[str, str]]] = None,
    max_tokens: int = 250,
    temperature: float = 0.3,
) -> str:
    """OpenAI-compatible chat completion.

    Args:
        system:      System prompt (role guidance).
        user:        Current user message.
        history:     Optional prior turns as
                     [{"role": "user"|"assistant", "content": "..."}].
                     Inserted between system and the current user message.
        max_tokens:  Response cap.
        temperature: Sampling temperature.

    Returns:
        The assistant's text reply.

    Raises:
        LLMUnavailableError: provider not configured or network error.
        LLMError:            non-200 response or malformed body.
    """
    if not settings.GROQ_API_KEY:
        raise LLMUnavailableError("GROQ_API_KEY is not set")

    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})

    base = settings.LLM_API_BASE_URL.rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as e:
            raise LLMUnavailableError(
                f"LLM HTTP request failed (url={url}): {e}"
            ) from e

    if resp.status_code != 200:
        raise LLMError(
            f"LLM HTTP {resp.status_code} (url={url}): {resp.text[:500]}"
        )

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"LLM response malformed: {e}") from e
