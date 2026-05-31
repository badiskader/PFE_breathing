"""
Pydantic schemas for the sensor-raw Kafka topic.

Canonical raw observation = location + 6 pollutants + 4 weather variables.
The producer validates rows against `SensorEvent` BEFORE publishing.
Consumers reuse the same model to deserialize, so the schema is defined
here, once, and nowhere else.

Architectural rule
------------------
`sensor_readings` (MongoDB) and the lakehouse Parquet rows must mirror
this schema 1:1. Derived layers (AQI, forecasting, recommendations) read
only the subsets they need via the module-level feature-set constants
below — they never reshape the raw event.
"""

from datetime import datetime
from typing import Any, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Feature taxonomy (single source of truth — used by AQI, forecast, analytics)
# ---------------------------------------------------------------------------

# US EPA pollutants — the only fields that participate in AQI computation.
POLLUTANT_COLUMNS: Tuple[str, ...] = (
    "PM25",
    "PM10",
    "NO2",
    "SO2",
    "CO",
    "O3",
)

# Weather / environmental context — stored for analytics, GIS, and future
# extensions of the forecasting model. NEVER used in AQI math.
WEATHER_COLUMNS: Tuple[str, ...] = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
)

# Location / coverage area of the sensor.
LOCATION_COLUMNS: Tuple[str, ...] = (
    "latitude",
    "longitude",
    "sensor_radius_km",
)

# AQI uses only pollutants (US EPA standard, Section 8 of the spec).
AQI_FEATURE_COLUMNS: Tuple[str, ...] = POLLUTANT_COLUMNS

# Mamba forecasting API contract today expects [PM25, PM10, NO2, SO2, CO, O3].
# When the model is retrained with weather exogenous inputs, extend this
# tuple — the forecast service reads from here, so no other code changes.
FORECAST_FEATURE_COLUMNS: Tuple[str, ...] = POLLUTANT_COLUMNS


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class SensorEvent(BaseModel):
    """One raw observation from one sensor at one timestamp.

    Fields mirror the source CSV after canonicalization (see
    `streaming/producer.py` for the CSV-column → canonical-name mapping).
    """

    model_config = ConfigDict(
        # A typo in a CSV column must not silently propagate into Mongo.
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    # --- Identity & time ---
    sensor_id: str = Field(..., min_length=1, description="Unique sensor identifier")
    timestamp: datetime = Field(..., description="Observation timestamp")

    # --- Location ---
    latitude: float = Field(..., description="Sensor centroid latitude (WGS84)")
    longitude: float = Field(..., description="Sensor centroid longitude (WGS84)")
    sensor_radius_km: float = Field(
        ..., ge=0, description="Coverage radius around the sensor centroid (km)"
    )

    # --- Pollutants (EPA AQI inputs) ---
    PM25: float = Field(..., ge=0, description="PM2.5 concentration (µg/m³)")
    PM10: float = Field(..., ge=0, description="PM10 concentration (µg/m³)")
    NO2: float = Field(..., ge=0, description="NO2 concentration (ppb or µg/m³)")
    SO2: float = Field(..., ge=0, description="SO2 concentration (ppb or µg/m³)")
    CO: float = Field(..., ge=0, description="CO concentration (ppm or µg/m³)")
    O3: float = Field(..., ge=0, description="O3 concentration (ppb or µg/m³)")

    # --- Weather / environmental context (NOT used by AQI) ---
    temperature_2m: float = Field(
        ..., description="Air temperature at 2m above ground (°C)"
    )
    relative_humidity_2m: float = Field(
        ..., description="Relative humidity at 2m above ground (%)"
    )
    wind_speed_10m: float = Field(
        ..., ge=0, description="Wind speed at 10m above ground (m/s)"
    )
    wind_direction_10m: float = Field(
        ..., description="Wind direction at 10m above ground (degrees, 0-360)"
    )

    # --- Validators ---

    @field_validator("latitude")
    @classmethod
    def _validate_latitude(cls, v: float) -> float:
        if not -90.0 <= v <= 90.0:
            raise ValueError(f"latitude {v} out of [-90, 90]")
        return v

    @field_validator("longitude")
    @classmethod
    def _validate_longitude(cls, v: float) -> float:
        if not -180.0 <= v <= 180.0:
            raise ValueError(f"longitude {v} out of [-180, 180]")
        return v

    @field_validator("temperature_2m")
    @classmethod
    def _validate_temperature(cls, v: float) -> float:
        # Lenient bounds — sanity check, not climatology.
        if not -90.0 <= v <= 70.0:
            raise ValueError(f"temperature_2m {v} °C is implausible")
        return v

    @field_validator("relative_humidity_2m")
    @classmethod
    def _validate_humidity(cls, v: float) -> float:
        # Some reanalysis sources emit slight overshoots; cap at 105.
        if not 0.0 <= v <= 105.0:
            raise ValueError(f"relative_humidity_2m {v} out of [0, 105]")
        return v

    @field_validator("wind_direction_10m")
    @classmethod
    def _validate_wind_direction(cls, v: float) -> float:
        if not 0.0 <= v <= 360.0:
            raise ValueError(f"wind_direction_10m {v} out of [0, 360]")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def _coerce_timestamp(cls, v: Any) -> Any:
        """Accept ISO 8601 strings, pandas Timestamps, or python datetimes.
        Reject NaN/NaT explicitly."""
        if v is None:
            raise ValueError("timestamp is required")
        if hasattr(v, "to_pydatetime"):  # pandas.Timestamp / np.datetime64
            return v.to_pydatetime()
        if isinstance(v, float) and v != v:  # NaN
            raise ValueError("timestamp is NaN")
        return v

    # --- Helpers (used by downstream services) ---

    def to_message(self) -> dict:
        """JSON-ready dict for Kafka publishing or Mongo insertion."""
        return self.model_dump(mode="json")

    def pollutants(self) -> dict:
        """Subset for AQI computation — pollutants only."""
        return {col: getattr(self, col) for col in POLLUTANT_COLUMNS}

    def weather(self) -> dict:
        """Subset for analytics / environmental context."""
        return {col: getattr(self, col) for col in WEATHER_COLUMNS}

    def forecast_features(self) -> list:
        """Feature vector for the Mamba forecast API, in canonical order."""
        return [getattr(self, col) for col in FORECAST_FEATURE_COLUMNS]
