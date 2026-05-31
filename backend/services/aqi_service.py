"""
US EPA AQI computation service.

Single source of truth for AQI logic. Breakpoint tables, sub-index calculation,
category mapping, and risk-level mapping all live here so the consumer stays
thin and other services (alerts, recommendations, chatbot Agent 4) can reuse
the same pure functions.

Inputs are assumed to be in µg/m³ (consistent with Open-Meteo / typical IoT
air-quality datasets). The service converts to EPA native units (ppb for
NO2/SO2, ppm for CO/O3) internally before applying breakpoints.

References
----------
- 40 CFR Appendix G to Part 58 (Uniform Air Quality Index)
- EPA Technical Assistance Document for the Reporting of Daily Air Quality
  (AQI Reporting Handbook, EPA-454/B-18-007, Sept 2018, updated 2024)
- PM2.5 breakpoints reflect the 2024 NAAQS revision (effective May 6, 2024).
"""

import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict

from streaming.schemas import POLLUTANT_COLUMNS, SensorEvent


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class AQIComputationError(ValueError):
    """Raised when AQI cannot be computed (missing/invalid pollutant values)."""


# ---------------------------------------------------------------------------
# Breakpoint tables — (c_low, c_high, aqi_low, aqi_high)
# All values are in each pollutant's EPA native unit (see UNIT_LABELS).
# ---------------------------------------------------------------------------

# PM2.5: 24-hour, µg/m³ (2024 NAAQS revision)
PM25_BREAKPOINTS: List[Tuple[float, float, int, int]] = [
    (0.0,    9.0,   0,   50),
    (9.1,    35.4,  51,  100),
    (35.5,   55.4,  101, 150),
    (55.5,   125.4, 151, 200),
    (125.5,  225.4, 201, 300),
    (225.5,  500.4, 301, 500),
]

# PM10: 24-hour, µg/m³
PM10_BREAKPOINTS: List[Tuple[float, float, int, int]] = [
    (0,    54,  0,   50),
    (55,   154, 51,  100),
    (155,  254, 101, 150),
    (255,  354, 151, 200),
    (355,  424, 201, 300),
    (425,  604, 301, 500),
]

# NO2: 1-hour, ppb
NO2_BREAKPOINTS: List[Tuple[float, float, int, int]] = [
    (0,     53,    0,   50),
    (54,    100,   51,  100),
    (101,   360,   101, 150),
    (361,   649,   151, 200),
    (650,   1249,  201, 300),
    (1250,  2049,  301, 500),
]

# SO2: 1-hour, ppb
SO2_BREAKPOINTS: List[Tuple[float, float, int, int]] = [
    (0,     35,    0,   50),
    (36,    75,    51,  100),
    (76,    185,   101, 150),
    (186,   304,   151, 200),
    (305,   604,   201, 300),
    (605,   1004,  301, 500),
]

# CO: 8-hour, ppm
CO_BREAKPOINTS: List[Tuple[float, float, int, int]] = [
    (0.0,   4.4,   0,   50),
    (4.5,   9.4,   51,  100),
    (9.5,   12.4,  101, 150),
    (12.5,  15.4,  151, 200),
    (15.5,  30.4,  201, 300),
    (30.5,  50.4,  301, 500),
]

# O3: 8-hour, ppm (extended with 1-hour breakpoints for very high values)
O3_BREAKPOINTS: List[Tuple[float, float, int, int]] = [
    (0.000, 0.054, 0,   50),
    (0.055, 0.070, 51,  100),
    (0.071, 0.085, 101, 150),
    (0.086, 0.105, 151, 200),
    (0.106, 0.200, 201, 300),
    (0.201, 0.504, 301, 500),
]

BREAKPOINTS: Dict[str, List[Tuple[float, float, int, int]]] = {
    "PM25": PM25_BREAKPOINTS,
    "PM10": PM10_BREAKPOINTS,
    "NO2":  NO2_BREAKPOINTS,
    "SO2":  SO2_BREAKPOINTS,
    "CO":   CO_BREAKPOINTS,
    "O3":   O3_BREAKPOINTS,
}


# ---------------------------------------------------------------------------
# Unit conversion: input (µg/m³) → EPA native unit
# Formula at 25°C, 1 atm:  ppb = µg/m³ × (24.45 / MW_g_per_mol)
# For CO and O3, EPA uses ppm = ppb / 1000.
# ---------------------------------------------------------------------------

INPUT_TO_EPA: Dict[str, float] = {
    "PM25": 1.0,         # µg/m³ → µg/m³
    "PM10": 1.0,         # µg/m³ → µg/m³
    "NO2":  0.5316,      # µg/m³ → ppb (MW 46.0055)
    "SO2":  0.3817,      # µg/m³ → ppb (MW 64.066)
    "CO":   0.0008729,   # µg/m³ → ppm (MW 28.01,  ÷1000)
    "O3":   0.0005094,   # µg/m³ → ppm (MW 48.00,  ÷1000)
}

UNIT_LABELS: Dict[str, str] = {
    "PM25": "µg/m³",
    "PM10": "µg/m³",
    "NO2":  "ppb",
    "SO2":  "ppb",
    "CO":   "ppm",
    "O3":   "ppm",
}

# EPA truncation: round concentration DOWN to this resolution before
# interpolating, per AQI Reporting Handbook §4. Prevents fall-through into
# the small gaps between consecutive breakpoint brackets.
TRUNCATION_RESOLUTION: Dict[str, float] = {
    "PM25": 0.1,
    "PM10": 1.0,
    "NO2":  1.0,
    "SO2":  1.0,
    "CO":   0.1,
    "O3":   0.001,
}


# ---------------------------------------------------------------------------
# AQI category & risk-level mapping
# ---------------------------------------------------------------------------

AQI_CATEGORY_GOOD = "Good"
AQI_CATEGORY_MODERATE = "Moderate"
AQI_CATEGORY_USG = "Unhealthy for Sensitive Groups"
AQI_CATEGORY_UNHEALTHY = "Unhealthy"
AQI_CATEGORY_VERY_UNHEALTHY = "Very Unhealthy"
AQI_CATEGORY_HAZARDOUS = "Hazardous"

CATEGORY_TO_RISK: Dict[str, str] = {
    AQI_CATEGORY_GOOD:            "low",
    AQI_CATEGORY_MODERATE:        "moderate",
    AQI_CATEGORY_USG:             "high",
    AQI_CATEGORY_UNHEALTHY:       "very_high",
    AQI_CATEGORY_VERY_UNHEALTHY:  "severe",
    AQI_CATEGORY_HAZARDOUS:       "severe",
}


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class AQIResult(BaseModel):
    """One AQI evaluation for one sensor at one timestamp."""

    model_config = ConfigDict(extra="forbid")

    sensor_id: str
    timestamp: datetime
    aqi_score: int
    aqi_category: str
    risk_level: str
    dominant_pollutant: str
    sub_indices: Dict[str, int]

    def to_doc(self) -> dict:
        """Mongo-ready dict (datetime preserved as BSON date)."""
        return self.model_dump(mode="python")


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _truncate_to_epa_resolution(pollutant: str, value: float) -> float:
    """Truncate concentration DOWN to EPA's reporting resolution."""
    res = TRUNCATION_RESOLUTION[pollutant]
    return math.floor(value / res) * res


def compute_sub_index(pollutant: str, value_ugm3: Optional[float]) -> Optional[int]:
    """Compute the AQI sub-index for one pollutant.

    Args:
        pollutant:    One of POLLUTANT_COLUMNS.
        value_ugm3:   Concentration in µg/m³ (Open-Meteo input convention).

    Returns:
        Integer AQI sub-index in [0, 500], or None if the input value is
        invalid (None, negative, or NaN). The caller decides whether a None
        sub-index aborts the AQI computation.
    """
    if pollutant not in BREAKPOINTS:
        raise ValueError(f"Unknown pollutant: {pollutant}")
    if value_ugm3 is None:
        return None
    if isinstance(value_ugm3, float) and math.isnan(value_ugm3):
        return None
    if value_ugm3 < 0:
        return None

    # 1. Convert to EPA native unit.
    epa_value = value_ugm3 * INPUT_TO_EPA[pollutant]
    # 2. Truncate to EPA reporting resolution.
    epa_value = _truncate_to_epa_resolution(pollutant, epa_value)
    # 3. Find the bracket and apply piecewise linear interpolation:
    #       AQI = ((aqi_hi - aqi_lo) / (c_hi - c_lo)) * (c - c_lo) + aqi_lo
    for c_lo, c_hi, aqi_lo, aqi_hi in BREAKPOINTS[pollutant]:
        if epa_value <= c_hi:
            return round(
                (aqi_hi - aqi_lo) / (c_hi - c_lo) * (epa_value - c_lo) + aqi_lo
            )

    # Above the highest defined bracket — cap at 500 (Hazardous).
    return 500


def compute_overall_aqi(sub_indices: Dict[str, int]) -> Tuple[int, str]:
    """Overall AQI = max(sub-indices). Returns (aqi, dominant_pollutant)."""
    valid = {k: v for k, v in sub_indices.items() if v is not None}
    if not valid:
        raise AQIComputationError("No valid sub-indices to compute AQI")
    dominant = max(valid, key=valid.__getitem__)
    return valid[dominant], dominant


def get_aqi_category(aqi: int) -> str:
    if aqi <= 50:  return AQI_CATEGORY_GOOD
    if aqi <= 100: return AQI_CATEGORY_MODERATE
    if aqi <= 150: return AQI_CATEGORY_USG
    if aqi <= 200: return AQI_CATEGORY_UNHEALTHY
    if aqi <= 300: return AQI_CATEGORY_VERY_UNHEALTHY
    return AQI_CATEGORY_HAZARDOUS


def get_risk_level(category: str) -> str:
    try:
        return CATEGORY_TO_RISK[category]
    except KeyError as e:
        raise AQIComputationError(f"Unknown AQI category: {category}") from e


def compute_aqi_from_pollutants(pollutants: Dict[str, float]) -> Dict[str, object]:
    """Compute AQI components from a pollutants dict (no sensor metadata needed).

    Shared by:
      * `build_aqi_result` (live AQI consumer, has a full SensorEvent)
      * forecast scheduler (predicted pollutants, no SensorEvent)

    Args:
        pollutants: Mapping {pollutant_name: concentration_µg_per_m3}.
            Must contain every entry in POLLUTANT_COLUMNS.

    Returns:
        {
            "aqi_score": int,
            "aqi_category": str,
            "risk_level": str,
            "dominant_pollutant": str,
            "sub_indices": Dict[str, int],
        }

    Raises:
        AQIComputationError if any pollutant produces an invalid sub-index.
    """
    sub_indices: Dict[str, Optional[int]] = {
        p: compute_sub_index(p, pollutants.get(p)) for p in POLLUTANT_COLUMNS
    }

    invalid = [k for k, v in sub_indices.items() if v is None]
    if invalid:
        raise AQIComputationError(f"Invalid sub-index for {invalid}")

    sub_indices_int: Dict[str, int] = {k: int(v) for k, v in sub_indices.items()}  # type: ignore[arg-type]
    overall_aqi, dominant = compute_overall_aqi(sub_indices_int)
    category = get_aqi_category(overall_aqi)
    risk = get_risk_level(category)

    return {
        "aqi_score": overall_aqi,
        "aqi_category": category,
        "risk_level": risk,
        "dominant_pollutant": dominant,
        "sub_indices": sub_indices_int,
    }


def build_aqi_result(event: SensorEvent) -> AQIResult:
    """Compute the full AQI result from a SensorEvent.

    Reads ONLY the pollutant fields (`event.pollutants()`); weather and
    location fields are ignored — they belong to the raw store, not AQI.

    Raises:
        AQIComputationError: if any pollutant produces an invalid sub-index.
    """
    try:
        components = compute_aqi_from_pollutants(event.pollutants())
    except AQIComputationError as e:
        # Re-raise with sensor context for better logging upstream.
        raise AQIComputationError(
            f"{e} (sensor_id={event.sensor_id}, timestamp={event.timestamp})"
        ) from e

    return AQIResult(
        sensor_id=event.sensor_id,
        timestamp=event.timestamp,
        **components,  # type: ignore[arg-type]
    )
