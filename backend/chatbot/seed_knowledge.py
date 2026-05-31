"""
Seed the `knowledge_chunks` collection with a small thesis-grade KB.

Run:
    python -m chatbot.seed_knowledge

Idempotent — uses chunk_id as the upsert key.

For a production-quality KB you'd ingest real PDFs (WHO guidelines, EPA
documents, medical journals) split into ~200–500 token chunks. This file
provides a curated mini-KB so the chatbot has something to retrieve from
during thesis testing.

Atlas Vector Search index (run this in the Atlas UI if USE_ATLAS_VECTOR_SEARCH=true):
    {
      "fields": [
        {
          "type": "vector",
          "path": "embedding",
          "numDimensions": 384,
          "similarity": "cosine"
        }
      ]
    }
"""

import asyncio
from datetime import datetime, timezone

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


# Thesis-grade seed corpus — short, factual, sourced.
SEED_CHUNKS = [
    {
        "chunk_id": "pm25_definition_001",
        "source": "WHO Air Quality Guidelines 2021",
        "content": (
            "PM2.5 are fine inhalable particles with diameters ≤ 2.5 micrometers. "
            "They penetrate deep into the lungs and enter the bloodstream, "
            "contributing to cardiovascular and respiratory disease."
        ),
    },
    {
        "chunk_id": "pm25_who_thresholds_001",
        "source": "WHO Air Quality Guidelines 2021",
        "content": (
            "WHO 2021 guideline for PM2.5: annual mean 5 µg/m³, 24-hour mean 15 µg/m³. "
            "Health effects begin at concentrations well below previous (2005) limits."
        ),
    },
    {
        "chunk_id": "pm10_definition_001",
        "source": "WHO Air Quality Guidelines 2021",
        "content": (
            "PM10 are inhalable particles ≤ 10 micrometers. WHO 2021 guideline: "
            "annual mean 15 µg/m³, 24-hour mean 45 µg/m³."
        ),
    },
    {
        "chunk_id": "ozone_health_001",
        "source": "EPA Integrated Science Assessment for Ozone (2020)",
        "content": (
            "Short-term ozone exposure causes airway inflammation, reduced lung "
            "function, and asthma exacerbation. Children, the elderly, and people "
            "with asthma are particularly sensitive."
        ),
    },
    {
        "chunk_id": "ozone_who_thresholds_001",
        "source": "WHO Air Quality Guidelines 2021",
        "content": (
            "WHO 2021 ozone guideline: 8-hour mean 100 µg/m³; peak-season mean 60 µg/m³."
        ),
    },
    {
        "chunk_id": "no2_health_001",
        "source": "EPA Integrated Science Assessment for NO2 (2016)",
        "content": (
            "NO2 inflames airway lining, worsens asthma symptoms, and increases "
            "respiratory infection risk. Traffic-related exposure is a major source."
        ),
    },
    {
        "chunk_id": "no2_who_thresholds_001",
        "source": "WHO Air Quality Guidelines 2021",
        "content": (
            "WHO 2021 NO2 guideline: annual mean 10 µg/m³, 24-hour mean 25 µg/m³."
        ),
    },
    {
        "chunk_id": "so2_health_001",
        "source": "EPA Air Quality Criteria for Sulfur Oxides",
        "content": (
            "SO2 causes bronchial constriction within minutes of exposure. "
            "Asthmatics can experience symptoms at concentrations as low as 200 ppb."
        ),
    },
    {
        "chunk_id": "co_health_001",
        "source": "EPA Air Quality Criteria for CO",
        "content": (
            "CO binds to hemoglobin, reducing oxygen delivery. People with "
            "cardiovascular disease are particularly vulnerable; symptoms include "
            "headache, dizziness, and impaired cognition."
        ),
    },
    {
        "chunk_id": "aqi_categories_001",
        "source": "US EPA AQI Reporting Handbook 2018 (updated 2024)",
        "content": (
            "US EPA AQI categories: 0–50 Good, 51–100 Moderate, 101–150 Unhealthy "
            "for Sensitive Groups, 151–200 Unhealthy, 201–300 Very Unhealthy, "
            "301–500 Hazardous."
        ),
    },
    {
        "chunk_id": "aqi_sensitive_groups_001",
        "source": "US EPA AQI Reporting Handbook 2018",
        "content": (
            "AQI Sensitive Groups include children, older adults, people with "
            "asthma, COPD, heart disease, pregnant women, and outdoor workers."
        ),
    },
    {
        "chunk_id": "asthma_air_pollution_001",
        "source": "GINA Global Strategy for Asthma 2023",
        "content": (
            "For asthmatics, PM2.5 and ozone are the primary triggers from outdoor "
            "air pollution. Indoor exposure reduction during high-AQI days reduces "
            "symptom frequency."
        ),
    },
    {
        "chunk_id": "cardiovascular_pm25_001",
        "source": "American Heart Association Scientific Statement 2010",
        "content": (
            "Long-term PM2.5 exposure is a causal contributor to cardiovascular "
            "mortality, especially in people with pre-existing coronary artery disease."
        ),
    },
    {
        "chunk_id": "outdoor_exercise_001",
        "source": "Health Canada Guidance",
        "content": (
            "During Unhealthy AQI days, healthy adults should consider reducing "
            "prolonged or heavy outdoor exertion. Sensitive groups should reschedule "
            "outdoor exercise to early morning or move indoors."
        ),
    },
    {
        "chunk_id": "wildfire_smoke_001",
        "source": "CDC Wildfire Smoke Guidance",
        "content": (
            "Wildfire smoke is dominated by PM2.5. N95 respirators reduce exposure; "
            "surgical and cloth masks do NOT effectively filter PM2.5."
        ),
    },
    {
        "chunk_id": "indoor_air_001",
        "source": "EPA Indoor Air Guidance",
        "content": (
            "Indoor PM2.5 can equal or exceed outdoor levels when smoke, cooking, "
            "or candles are present. HEPA air purifiers reduce indoor PM2.5 by 50–80%."
        ),
    },
]


async def seed() -> None:
    await connect_to_mongo()
    await ensure_knowledge_chunks_indexes()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ops = []
    logger.info("Embedding %d seed chunks (first call loads the model)…", len(SEED_CHUNKS))
    for ch in SEED_CHUNKS:
        emb = embed_text_sync(ch["content"])
        ops.append(
            UpdateOne(
                {"chunk_id": ch["chunk_id"]},
                {
                    "$set": {
                        "chunk_id": ch["chunk_id"],
                        "source": ch["source"],
                        "content": ch["content"],
                        "embedding": emb,
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
        )

    result = await knowledge_chunks().bulk_write(ops, ordered=False)
    logger.info(
        "Seed complete | upserted=%d modified=%d total_chunks=%d",
        result.upserted_count,
        result.modified_count,
        len(SEED_CHUNKS),
    )

    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(seed())
