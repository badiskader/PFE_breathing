"""
Ingest a directory of PDFs into the `knowledge_chunks` collection.

For each PDF in the input directory:
  1. Extract text page by page with pypdf.
  2. Split into ~CHUNK_WORDS-word windows with CHUNK_OVERLAP words of overlap.
  3. Embed each chunk with sentence-transformers.
  4. Upsert into Mongo keyed by `chunk_id = "<file_stem>_p<NNNN>"`.

Usage:
    python -m chatbot.ingest_pdfs <pdf_directory>

Re-running on the same directory is safe (upserts). Re-running after
editing one PDF: change its file name OR delete its old chunks first
(chunk_ids embed the file stem, so a renamed file produces a fresh set).

Designed to complement `chatbot/seed_knowledge.py`. Seed gives you a
hand-curated mini-KB; this script lets you scale up to real WHO/EPA
documents for a stronger thesis demo.
"""

import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from pymongo import UpdateOne

from chatbot.embedder import embed_text_sync
from core.logger import get_logger
from core.mongo_client import (
    close_mongo_connection,
    connect_to_mongo,
    ensure_knowledge_chunks_indexes,
    knowledge_chunks,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

CHUNK_WORDS = 300       # ~ 400-500 tokens for a typical sentence-transformers model
CHUNK_OVERLAP = 40      # context bleed between adjacent chunks
MIN_CHUNK_WORDS = 30    # drop micro-chunks (table footers, page numbers, etc.)


# ---------------------------------------------------------------------------
# PDF → text → chunks
# ---------------------------------------------------------------------------

def _extract_pdf_text(path: Path) -> str:
    """Concatenate text from every page of a PDF. Returns "" if extraction fails."""
    try:
        # Imported lazily so the rest of the chatbot package doesn't pull pypdf.
        import pypdf
    except ImportError as e:
        raise SystemExit(
            "pypdf is required for PDF ingestion. Install with: pip install pypdf"
        ) from e

    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as e:
        logger.warning("Could not open PDF %s: %s", path.name, e)
        return ""

    parts: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception as e:
            logger.warning("Page %d of %s failed: %s", i, path.name, e)
            continue
        parts.append(t)

    return "\n\n".join(parts)


def _clean(text: str) -> str:
    """Light cleanup so chunks are LLM-friendly."""
    # Collapse hyphenated line breaks: "exam-\nple" → "example"
    text = re.sub(r"-\n", "", text)
    # Newlines → spaces (preserve paragraph breaks as double-space).
    text = re.sub(r"\n{2,}", "  ", text)
    text = re.sub(r"\n", " ", text)
    # Squash whitespace.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _chunk(text: str) -> Iterable[str]:
    """Yield ~CHUNK_WORDS-word windows with CHUNK_OVERLAP overlap."""
    words = text.split()
    if len(words) < MIN_CHUNK_WORDS:
        return
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)
    for start in range(0, len(words), step):
        window = words[start : start + CHUNK_WORDS]
        if len(window) < MIN_CHUNK_WORDS:
            continue
        yield " ".join(window)


# ---------------------------------------------------------------------------
# Ingestion per PDF
# ---------------------------------------------------------------------------

async def _ingest_one(path: Path) -> int:
    """Ingest one PDF. Returns the number of chunks upserted."""
    source = path.stem
    logger.info("Ingesting %s", path.name)

    raw = _extract_pdf_text(path)
    if not raw:
        logger.warning("Skipping %s (no extractable text)", path.name)
        return 0

    cleaned = _clean(raw)
    chunks = list(_chunk(cleaned))
    if not chunks:
        logger.warning("Skipping %s (no chunks of usable size)", path.name)
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ops: List[UpdateOne] = []
    for idx, content in enumerate(chunks):
        chunk_id = f"{source}_p{idx:04d}"
        emb = embed_text_sync(content)
        ops.append(
            UpdateOne(
                {"chunk_id": chunk_id},
                {
                    "$set": {
                        "chunk_id": chunk_id,
                        "source": source,
                        "content": content,
                        "embedding": emb,
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
        )

    result = await knowledge_chunks().bulk_write(ops, ordered=False)
    logger.info(
        "Ingested %s | chunks=%d upserted=%d modified=%d",
        path.name,
        len(chunks),
        result.upserted_count,
        result.modified_count,
    )
    return len(chunks)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main(pdf_dir: Path) -> None:
    if not pdf_dir.exists():
        raise SystemExit(f"Directory does not exist: {pdf_dir}")
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {pdf_dir}")

    await connect_to_mongo()
    await ensure_knowledge_chunks_indexes()

    total_chunks = 0
    try:
        for pdf in pdfs:
            try:
                total_chunks += await _ingest_one(pdf)
            except Exception as e:
                logger.exception("Failed to ingest %s: %s", pdf.name, e)
    finally:
        await close_mongo_connection()

    logger.info("All done | files=%d total_chunks=%d", len(pdfs), total_chunks)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python -m chatbot.ingest_pdfs <pdf_directory>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    asyncio.run(main(Path(sys.argv[1])))
