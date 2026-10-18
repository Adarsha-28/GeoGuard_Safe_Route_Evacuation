"""Pydantic schemas for Flood Risk Queries and Weather Synchronization."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RiskPointResponse(BaseModel):
    """Spatial risk evaluation for user coordinates."""

    latitude: float
    longitude: float
    risk_level: str
    probability: Optional[float] = None
    note: str = "Current stored risk based on nearest monitored Chennai sector."


class RiskDetailResponse(BaseModel):
    """Detailed deterministic risk breakdown for specific grid sector."""

    grid_id: int
    place_name: str
    risk_level: str
    risk_score: float
    probability: Optional[float] = None
    rainfall_mm: float
    elevation_m: float
    distance_to_water_m: float
    scoring_method: str = "Deterministic Multi-Criteria (Rainfall, Inverted Elevation, Water Proximity)"


class WeatherSyncResponse(BaseModel):
    """Response acknowledging telemetry sync from Open-Meteo."""

    message: str
    measured_rainfall_mm: float
    synced_at: str


class ContributingFeature(BaseModel):
    """Interpretability feature contribution."""

    feature: str
    value: str
    impact: str


class MLPredictionRequest(BaseModel):
    """Payload to request an empirical ML flood risk forecast."""

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate")
    rainfall_mm: Optional[float] = Field(None, ge=0.0, description="Optional override for current rainfall in mm")


class MLPredictionResponse(BaseModel):
    """Empirical ML flood risk prediction forecast response."""

    grid_id: Optional[int] = None
    place_name: Optional[str] = None
    latitude: float
    longitude: float
    prediction: str = Field(..., description="Categorical risk forecast (Low, Moderate, High, Severe)")
    probability: float = Field(..., ge=0.0, le=1.0, description="Statistical flood probability from ML model")
    model_version: str = Field("v3.0.0", description="Active prediction model version tag")
    algorithm: str = Field("Gradient Boosting", description="Underlying ML algorithm")
    prediction_horizon: str = Field("24-Hour Flood Inundation Hazard", description="Forecast time window")
    is_fallback: bool = Field(False, description="True if prediction fell back to deterministic model")
    contributing_features: list[ContributingFeature] = Field(default_factory=list)
