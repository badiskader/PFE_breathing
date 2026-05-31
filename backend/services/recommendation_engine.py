"""
Recommendation engine — Type 1 (dashboard) and Type 2 (chatbot).

Two strictly separated layers:

  LAYER A — Rule engine (deterministic, explainable, testable)
    Pure Python. Input: vulnerability category + 12h forecast. Output:
    structured RuleRecommendationResult (urgency, flagged pollutants,
    trajectory, key risks, per-pollutant scores). Fully inspectable —
    this is the academic core of the thesis.

  LAYER B — LLM text generator (Groq today; OpenAI-compatible API)
    Pure presentation. Input: rule output. Output: 2-3 sentence
    recommendation text. Swappable by changing `LLM_API_BASE_URL`
    (Groq → OpenAI → Ollama, same code).

  Smart regeneration (should_regenerate_recommendation)
    Gates Layer B. Cheap rule_output is always refreshed; the LLM is
    only called when the rule layer's findings have materially changed
    or a configurable interval has elapsed.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from core.config import settings
from core.logger import get_logger
from services.aqi_service import get_aqi_category
from services.llm_client import LLMError, LLMUnavailableError, call_chat_llm
from streaming.schemas import POLLUTANT_COLUMNS

logger = get_logger(__name__)


# ============================================================================
# CONSTANTS — vulnerability taxonomy, urgency levels, threshold tables
# ============================================================================

# Vulnerability categories (Section 10 of the architecture spec).
VULNERABILITY_GENERAL = "générale"
VULNERABILITY_SENSIBLE = "sensible"
VULNERABILITY_VULNERABLE = "vulnérable"

VULNERABILITY_CATEGORIES: Tuple[str, ...] = (
    VULNERABILITY_GENERAL,
    VULNERABILITY_SENSIBLE,
    VULNERABILITY_VULNERABLE,
)

# Urgency levels.
URGENCY_SAFE = "safe"
URGENCY_CAUTION = "caution"
URGENCY_AVOID = "avoid"
URGENCY_DANGER = "danger"

URGENCY_BY_SCORE: Dict[int, str] = {
    0: URGENCY_SAFE,
    1: URGENCY_CAUTION,
    2: URGENCY_AVOID,
    3: URGENCY_DANGER,
}

# AQI trajectory labels.
TRAJECTORY_RISING = "rising"
TRAJECTORY_STABLE = "stable"
TRAJECTORY_FALLING = "falling"

# Per-pollutant concentration thresholds for (caution, avoid, danger).
# All values in µg/m³ — same unit as the stored sensor data.
# Reference: WHO 2021 air-quality guidelines + EPA AQI category boundaries,
# adapted per vulnerability category.
#
# - vulnérable : strictest tier (pregnancy, elderly, chronic disease, kids)
# - sensible   : strict on PM25 + O3 ("critical"), moderate on NO2 + CO
# - générale   : reference public-health tier (WHO/EPA)
THRESHOLDS_BY_CATEGORY: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    VULNERABILITY_VULNERABLE: {
        "PM25": (10,   20,    35),
        "PM10": (25,   50,    100),
        "NO2":  (15,   40,    100),
        "SO2":  (20,   50,    125),
        "CO":   (3000, 7000,  12000),
        "O3":   (60,   100,   160),
    },
    VULNERABILITY_SENSIBLE: {
        # PM25 + O3: critical sensitivity (asthma, allergies)
        "PM25": (15,   25,    45),
        "O3":   (80,   130,   200),
        # NO2 + CO: moderate sensitivity
        "NO2":  (25,   80,    180),
        "CO":   (4000, 10000, 20000),
        # PM10 + SO2: standard
        "PM10": (50,   100,   200),
        "SO2":  (60,   200,   500),
    },
    VULNERABILITY_GENERAL: {
        "PM25": (25,   55,    150),
        "PM10": (50,   150,   350),
        "NO2":  (40,   200,   600),
        "SO2":  (75,   300,   800),
        "CO":   (5000, 15000, 35000),
        "O3":   (120,  200,   380),
    },
}

# Short, generic health risks attached when a pollutant is flagged.
# Ordered most-to-least relevant per pollutant.
POLLUTANT_RISKS: Dict[str, List[str]] = {
    "PM25": ["respiratory irritation", "cardiovascular stress"],
    "PM10": ["throat and eye irritation"],
    "NO2":  ["asthma aggravation", "airway inflammation"],
    "SO2":  ["bronchial constriction"],
    "CO":   ["reduced oxygen delivery", "headache"],
    "O3":   ["reduced exercise tolerance", "asthma trigger"],
}


# ============================================================================
# Errors
# ============================================================================

class RecommendationError(Exception):
    """Base error for the recommendation engine."""


# ============================================================================
# Output model — fully inspectable rule-layer result
# ============================================================================

class RuleRecommendationResult(BaseModel):
    """Deterministic rule-engine output.

    The scheduler stores this whole object inside the
    `rule_output` field of a dashboard_recommendations document. Keeping
    every intermediate result (per-pollutant score, max forecast value) in
    the model is intentional — the thesis needs the rule layer to be
    auditable from raw Mongo dumps.
    """

    model_config = ConfigDict(extra="forbid")

    vulnerability_category: str
    forecast_aqi_max: int
    forecast_category: str
    aqi_trajectory: str

    flagged_pollutants: List[str] = Field(default_factory=list)
    urgency_level: str
    key_risks: List[str] = Field(default_factory=list)

    # Diagnostics — required for thesis-grade inspectability.
    pollutant_scores: Dict[str, int] = Field(default_factory=dict)
    pollutant_max_values: Dict[str, float] = Field(default_factory=dict)


# ============================================================================
# VULNERABILITY-CATEGORY COMPUTATION (used at user onboarding & profile updates)
# ============================================================================

# Score thresholds — clearly named so the thesis can defend them.
VULNERABILITY_VULNERABLE_THRESHOLD = 0.60
VULNERABILITY_SENSIBLE_THRESHOLD = 0.30


def compute_vulnerability_category(
    profile: dict,
) -> Tuple[str, float, List[str]]:
    """Derive the vulnerability category from a user profile.

    Inputs (all optional except age):
        age, is_pregnant, asthma, cardiovascular, chronic_diseases (list),
        smoking_status ("never"/"former"/"current"), outdoor_worker,
        intense_sport, low_socioeconomic, pollution_sensitivity ("low"/
        "medium"/"high"), activity_level ("sedentary"/"moderate"/"active").

    Returns:
        (category, score_0_to_1, contributing_factors)

    The score and factors are persisted alongside the category for
    auditability — the thesis explicitly mentions they should be
    inspectable for debugging and category-assignment defense.
    """
    score = 0.0
    factors: List[str] = []

    age = int(profile.get("age") or 0)
    if age >= 65:
        score += 0.35
        factors.append(f"age>=65 ({age})")
    elif age <= 12:
        score += 0.30
        factors.append(f"age<=12 ({age})")
    elif age >= 55:
        score += 0.15
        factors.append(f"age>=55 ({age})")

    if profile.get("is_pregnant"):
        score += 0.40
        factors.append("pregnant")

    if profile.get("asthma"):
        score += 0.35
        factors.append("asthma")

    if profile.get("cardiovascular"):
        score += 0.35
        factors.append("cardiovascular")

    chronic = profile.get("chronic_diseases") or []
    if chronic:
        # Capped contribution so a long list doesn't dominate.
        score += min(0.30, 0.10 * len(chronic))
        factors.append(f"chronic_diseases({len(chronic)})")

    if profile.get("smoking_status") == "current":
        score += 0.20
        factors.append("current_smoker")

    if profile.get("outdoor_worker"):
        score += 0.20
        factors.append("outdoor_worker")

    if profile.get("intense_sport"):
        score += 0.15
        factors.append("intense_sport")

    if profile.get("low_socioeconomic"):
        score += 0.10
        factors.append("low_socioeconomic")

    sensitivity = profile.get("pollution_sensitivity")
    if sensitivity == "high":
        score += 0.20
        factors.append("high_sensitivity")
    elif sensitivity == "medium":
        score += 0.10
        factors.append("medium_sensitivity")

    score = min(1.0, round(score, 3))

    if score >= VULNERABILITY_VULNERABLE_THRESHOLD:
        category = VULNERABILITY_VULNERABLE
    elif score >= VULNERABILITY_SENSIBLE_THRESHOLD:
        category = VULNERABILITY_SENSIBLE
    else:
        category = VULNERABILITY_GENERAL

    return category, score, factors


# ============================================================================
# LAYER A — RULE ENGINE
# ============================================================================

def _compute_trajectory(predictions: List[dict]) -> str:
    """Compare the average AQI of the early window vs the late window."""
    aqis = [int(p["predicted_aqi"]) for p in predictions if "predicted_aqi" in p]
    if len(aqis) < 4:
        return TRAJECTORY_STABLE

    third = max(1, len(aqis) // 3)
    early = sum(aqis[:third]) / third
    late = sum(aqis[-third:]) / third
    delta = late - early

    if delta > 10:
        return TRAJECTORY_RISING
    if delta < -10:
        return TRAJECTORY_FALLING
    return TRAJECTORY_STABLE


def _score_pollutant(max_value: float, thresholds: Tuple[float, float, float]) -> int:
    """Map a pollutant's max forecast concentration to a 0–3 score."""
    caution, avoid, danger = thresholds
    if max_value >= danger:
        return 3
    if max_value >= avoid:
        return 2
    if max_value >= caution:
        return 1
    return 0


def _derive_key_risks(flagged: List[str], limit: int = 4) -> List[str]:
    """Collect distinct health risks across flagged pollutants."""
    risks: List[str] = []
    seen = set()
    for p in flagged:
        for r in POLLUTANT_RISKS.get(p, []):
            if r not in seen:
                seen.add(r)
                risks.append(r)
            if len(risks) >= limit:
                return risks
    return risks


def compute_rule_based_recommendation(
    vulnerability_category: str,
    forecast_predictions: List[dict],
) -> RuleRecommendationResult:
    """Run the deterministic rule engine over a 12-hour forecast.

    Args:
        vulnerability_category: One of VULNERABILITY_CATEGORIES.
        forecast_predictions: List of forecasted hours (predictions[].predictions
            from the `predictions` collection). Each hour must contain
            `predicted_aqi` and the 6 canonical pollutant fields in µg/m³.

    Returns:
        Complete RuleRecommendationResult — every intermediate result preserved.
    """
    if vulnerability_category not in THRESHOLDS_BY_CATEGORY:
        raise RecommendationError(
            f"Unknown vulnerability category: {vulnerability_category}"
        )
    if not forecast_predictions:
        raise RecommendationError("forecast_predictions is empty")

    thresholds = THRESHOLDS_BY_CATEGORY[vulnerability_category]

    # AQI summary over the horizon.
    aqis = [int(p["predicted_aqi"]) for p in forecast_predictions if "predicted_aqi" in p]
    if not aqis:
        raise RecommendationError("No predicted_aqi values found in forecast")
    forecast_aqi_max = max(aqis)
    forecast_category = get_aqi_category(forecast_aqi_max)
    trajectory = _compute_trajectory(forecast_predictions)

    # Max forecast concentration per pollutant.
    pollutant_max: Dict[str, float] = {}
    for p in POLLUTANT_COLUMNS:
        values = [
            float(h[p]) for h in forecast_predictions
            if p in h and h[p] is not None
        ]
        if values:
            pollutant_max[p] = max(values)

    # Score each pollutant against this category's thresholds.
    pollutant_scores: Dict[str, int] = {}
    for p in POLLUTANT_COLUMNS:
        if p not in thresholds or p not in pollutant_max:
            continue
        pollutant_scores[p] = _score_pollutant(pollutant_max[p], thresholds[p])

    # Flagged = anything not safe (score >= 1).
    flagged = [p for p, s in pollutant_scores.items() if s >= 1]

    # Overall urgency = highest individual pollutant score.
    max_score = max(pollutant_scores.values()) if pollutant_scores else 0
    urgency = URGENCY_BY_SCORE[max_score]

    key_risks = _derive_key_risks(flagged)

    return RuleRecommendationResult(
        vulnerability_category=vulnerability_category,
        forecast_aqi_max=forecast_aqi_max,
        forecast_category=forecast_category,
        aqi_trajectory=trajectory,
        flagged_pollutants=flagged,
        urgency_level=urgency,
        key_risks=key_risks,
        pollutant_scores=pollutant_scores,
        pollutant_max_values=pollutant_max,
    )


# ============================================================================
# LAYER B — LLM TEXT GENERATOR (Groq via OpenAI-compatible API)
# ============================================================================

_SYSTEM_PROMPT = (
    "You are an air quality health advisor. "
    "Generate a concise, actionable recommendation for a specific user "
    "vulnerability category. Strict rules:\n"
    "  - 2 sentences MAX.\n"
    "  - Do NOT mention AQI numbers directly.\n"
    "  - Focus on what the user should DO (or avoid).\n"
    "  - Match the urgency level provided in the context.\n"
    "  - If trajectory is 'rising', warn the user conditions may worsen soon.\n"
    "  - If trajectory is 'falling', reassure but remind to stay cautious.\n"
    "  - Prefer French phrasing for end-user-facing language."
)


def _build_user_prompt(rule: RuleRecommendationResult) -> str:
    """Format the structured rule output into a user-side LLM prompt."""
    flagged = ", ".join(rule.flagged_pollutants) if rule.flagged_pollutants else "none"
    risks = "; ".join(rule.key_risks) if rule.key_risks else "none specific"
    return (
        f"Vulnerability category: {rule.vulnerability_category}\n"
        f"Urgency level: {rule.urgency_level}\n"
        f"Forecast AQI category over next 12 hours: {rule.forecast_category}\n"
        f"AQI trajectory: {rule.aqi_trajectory}\n"
        f"Flagged pollutants: {flagged}\n"
        f"Key health risks: {risks}\n"
        f"Write the recommendation."
    )


def _fallback_text(rule: RuleRecommendationResult) -> str:
    """Deterministic text when the LLM is unavailable.

    Lets the system keep producing valid dashboard_recommendations during
    development (no API key) or in degraded mode (LLM down). The thesis
    can present rule_output as the primary scientific artifact even if
    the LLM text is the fallback variant.
    """
    flagged = ", ".join(rule.flagged_pollutants) if rule.flagged_pollutants else "aucun"
    if rule.urgency_level == URGENCY_SAFE:
        return "Conditions favorables. Vous pouvez maintenir vos activités habituelles."
    if rule.urgency_level == URGENCY_CAUTION:
        return (
            f"Vigilance recommandée. Polluants à surveiller : {flagged}. "
            f"Limitez les efforts intenses en extérieur si vous êtes sensible."
        )
    if rule.urgency_level == URGENCY_AVOID:
        return (
            f"Évitez les activités extérieures prolongées. "
            f"Pollution préoccupante : {flagged}. Restez à l'intérieur si possible."
        )
    return (
        f"Conditions dangereuses : {flagged}. "
        f"Restez à l'intérieur. Évitez tout effort physique extérieur."
    )


async def generate_recommendation_text(rule: RuleRecommendationResult) -> str:
    """Produce the natural-language recommendation.

    Tries the LLM first; falls back to a deterministic template if the LLM
    is unavailable. The fallback path is logged at WARNING so degraded
    operation is visible.
    """
    try:
        return await call_chat_llm(
            _SYSTEM_PROMPT,
            _build_user_prompt(rule),
            max_tokens=180,
            temperature=0.3,
        )
    except LLMUnavailableError as e:
        logger.warning("LLM unavailable, using fallback text: %s", e)
        return _fallback_text(rule)
    except LLMError as e:
        logger.error("LLM error, using fallback text: %s", e)
        return _fallback_text(rule)


# ============================================================================
# SMART REGENERATION — gates the LLM call
# ============================================================================

def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def should_regenerate_recommendation(
    previous_doc: Optional[dict],
    new_rule: RuleRecommendationResult,
    *,
    regen_interval_hours: int,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Decide whether `recommendation_text` should be regenerated.

    Returns:
        (should_regenerate, reason). The rule_output is ALWAYS overwritten
        downstream — only the LLM call is gated.
    """
    if previous_doc is None:
        return True, "no previous recommendation exists"

    prev_rule = previous_doc.get("rule_output") or {}

    prev_urgency = prev_rule.get("urgency_level")
    if prev_urgency != new_rule.urgency_level:
        return True, f"urgency changed: {prev_urgency} → {new_rule.urgency_level}"

    prev_category = previous_doc.get("forecast_category")
    if prev_category != new_rule.forecast_category:
        return True, (
            f"AQI category changed: {prev_category} → {new_rule.forecast_category}"
        )

    prev_generated_at = previous_doc.get("generated_at")
    if isinstance(prev_generated_at, datetime):
        now = now or _utc_now_naive()
        elapsed_hours = (now - prev_generated_at).total_seconds() / 3600.0
        if elapsed_hours >= regen_interval_hours:
            return True, (
                f"regen interval elapsed "
                f"({elapsed_hours:.1f}h >= {regen_interval_hours}h)"
            )

    return False, "no significant change"
