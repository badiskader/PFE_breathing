"""
Sentence-Transformers embedder.

Singleton-lazy: the model is downloaded + loaded on the FIRST call only.
First chat message after process startup will pay ~5–10s; subsequent
embeddings are ~10–50ms on CPU.

The encode call is sync and blocking, so the async wrapper runs it on a
thread to keep the FastAPI event loop responsive.
"""

import asyncio
import threading
from typing import List

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Lazy-load the SentenceTransformer model (thread-safe)."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading embedding model %s (first-call cost)",
                settings.EMBEDDING_MODEL,
            )
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info(
                "Embedding model loaded, dim=%d",
                _model.get_sentence_embedding_dimension(),
            )
    return _model


def embed_text_sync(text: str) -> List[float]:
    """Synchronous embedding (used inside threadpool / scripts)."""
    vec = _get_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


async def embed_text_async(text: str) -> List[float]:
    """Async embedding — offloads the CPU-bound encode to a thread."""
    return await asyncio.to_thread(embed_text_sync, text)


def embedding_dim() -> int:
    return _get_model().get_sentence_embedding_dimension()
