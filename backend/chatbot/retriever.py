"""
Vector retrieval over `knowledge_chunks`.

Two paths, switched by `USE_ATLAS_VECTOR_SEARCH`:

  - Atlas: uses MongoDB Atlas `$vectorSearch` aggregation against a
    pre-created vector index. Required for production / large KBs.

  - Local: in-Python cosine similarity across the whole collection.
    Works on local single-node Mongo and is fine for thesis-scale
    KBs (≤ a few thousand chunks).

Retrieval is intentionally isolated from agents — they call
`retrieve_relevant_chunks(query, top_k)` and never touch Mongo or
the embedder directly.
"""

import asyncio
from typing import List

import numpy as np
from pydantic import BaseModel

from chatbot.embedder import embed_text_async
from core.config import settings
from core.logger import get_logger
from core.mongo_client import knowledge_chunks

logger = get_logger(__name__)


class RetrievedChunk(BaseModel):
    chunk_id: str
    source: str
    content: str
    score: float


# ---------------------------------------------------------------------------
# Atlas path
# ---------------------------------------------------------------------------

async def _retrieve_via_atlas(query_vector: List[float], top_k: int) -> List[RetrievedChunk]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.ATLAS_VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": max(50, top_k * 10),
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "chunk_id": 1,
                "source": 1,
                "content": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    docs = await knowledge_chunks().aggregate(pipeline).to_list(length=top_k)
    return [RetrievedChunk(**d) for d in docs]


# ---------------------------------------------------------------------------
# Local cosine fallback (works without Atlas)
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


async def _retrieve_via_local_cosine(
    query_vector: List[float], top_k: int
) -> List[RetrievedChunk]:
    # Pull all chunks once. For thesis-scale KBs (<10k chunks) this is fine.
    cursor = knowledge_chunks().find(
        {"embedding": {"$exists": True}},
        projection={"_id": 0, "chunk_id": 1, "source": 1, "content": 1, "embedding": 1},
    )
    docs = await cursor.to_list(length=None)
    if not docs:
        return []

    qv = np.asarray(query_vector, dtype=np.float32)

    def _score_all():
        scored = []
        for d in docs:
            emb = d.get("embedding")
            if not emb:
                continue
            score = _cosine_similarity(qv, np.asarray(emb, dtype=np.float32))
            scored.append((score, d))
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[:top_k]

    top = await asyncio.to_thread(_score_all)
    return [
        RetrievedChunk(
            chunk_id=d["chunk_id"],
            source=d.get("source", ""),
            content=d["content"],
            score=float(score),
        )
        for score, d in top
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def retrieve_relevant_chunks(query: str, top_k: int = None) -> List[RetrievedChunk]:
    """Embed the query, retrieve top_k chunks via the configured backend."""
    top_k = top_k or settings.RAG_TOP_K
    query_vector = await embed_text_async(query)

    if settings.USE_ATLAS_VECTOR_SEARCH:
        try:
            return await _retrieve_via_atlas(query_vector, top_k)
        except Exception as e:
            logger.warning(
                "Atlas vector search failed (%s), falling back to local cosine", e
            )

    return await _retrieve_via_local_cosine(query_vector, top_k)
