"""Pydantic schemas for GeoGuard V5 Predictive Intelligence & Decision Support."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ContributingFeatureSchema(BaseModel):
    """Model-supported feature attribution."""
    feature: str = Field(..., description="Feature variable key")
    name: str = Field(..., description="Human-readable feature name")
    value: str = Field(..., description="Current observed or forecasted value")
    relative_importance: float = Field(..., description="Model global feature importance weight")
    direction: str = Field(..., description="Impact direction (Hazard or Protective)")
    attribution_type: str = Field(..., description="Methodology label")


class ForecastPredictionItem(BaseModel):
    """Prediction item for an individual sector at a designated horizon."""
    grid_id: int
    grid_name: str
    prediction: str
    probability: float
    risk_level: str
    confidence: float
    confidence_category: str
    model_version: str
    horizon: str
    prediction_time: str
    rainfall_mm: float
    rainfall_3d_mm: float
    rainfall_7d_mm: float
    elevation_m: float
    distance_to_water_m: float
    is_fallback: bool
    fallback_reason: Optional[str] = None
    features: dict[str, Any] = {}
    contributing_features: list[ContributingFeatureSchema] = []


class ForecastResponse(BaseModel):
    """Response envelope for multi-horizon forecast predictions."""
    horizon: str
    total_grids: int
    active_model: str
    generated_at: str
    predictions: list[ForecastPredictionItem]


class RiskTrendHistoryItem(BaseModel):
    """Historical snapshot item for risk trends."""
    id: int
    grid_id: int
    horizon: str
    predicted_at: Optional[str]
    risk_level: str
    probability: float
    confidence: float
    confidence_category: str
    rainfall_mm: float
    rainfall_3d_mm: float
    rainfall_7d_mm: float
    model_version: str
    trigger_type: str
    is_fallback: bool
    features: dict[str, Any] = {}
    contributing_features: list[dict[str, Any]] = []


class RiskTrendResponse(BaseModel):
    """Response envelope for grid risk trend telemetry."""
    grid_id: int
    grid_name: str
    horizon: str
    query_window_hours: int
    data_points_count: int
    current_risk_level: str
    current_probability: float
    current_confidence: float
    overall_trend: str
    overall_probability_delta: float
    history: list[RiskTrendHistoryItem]


class ZonePriorityItem(BaseModel):
    """Triage priority scoring item for a monitored sector."""
    grid_id: int
    grid_name: str
    priority_score: float
    priority_rank: int
    priority_category: str
    risk_level: str
    predicted_probability: float
    probability_delta: float
    rainfall_accumulation_mm: float
    shelter_accessibility_score: float
    confidence: float
    horizon: str
    calculated_at: Optional[str]
    recommended_action: str


class ZonePriorityResponse(BaseModel):
    """Response envelope for zone prioritization triage."""
    total_zones: int
    horizon: str
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    priorities: list[ZonePriorityItem]


class OperationalTimelineEvent(BaseModel):
    """Event ledger item in command center timeline."""
    id: int
    event_type: str
    category: str
    severity: str
    message: str
    grid_id: Optional[int]
    grid_name: Optional[str]
    metadata: dict[str, Any] = {}
    created_at: Optional[str]


class TimelineResponse(BaseModel):
    """Response envelope for operational event timeline."""
    total_events: int
    query_window_hours: int
    events: list[OperationalTimelineEvent]


class ShelterIntelligenceItem(BaseModel):
    """Intelligence assessment item for a relief shelter."""
    id: int
    name: str
    latitude: float
    longitude: float
    address: str
    capacity: int
    available_capacity: int
    capacity_utilization_pct: float
    surrounding_flood_risk: str
    suitability_score: float
    warning_status: str
    recommendation: str
    distance_km: Optional[float]
    facilities: str
    contact: str
    is_active: bool


class ShelterIntelligenceResponse(BaseModel):
    """Response envelope for shelter intelligence."""
    total_shelters: int
    optimal_count: int
    elevated_risk_count: int
    at_capacity_count: int
    shelters: list[ShelterIntelligenceItem]


class RouteIntelligenceResponse(BaseModel):
    """Response envelope for candidate evacuation route intelligence."""
    shelter_id: int
    shelter_name: str
    shelter_available_capacity: int
    shelter_surrounding_risk: str
    source: dict[str, float]
    destination: dict[str, float]
    distance_meters: float
    distance_km: float
    duration_seconds: float
    duration_minutes: float
    maximum_flood_risk: str
    average_route_risk: float
    percent_route_in_risky_zones: float
    safety_score: float
    status: str
    advisory_disclaimer: str
    advisory_text: str
    geometry: Optional[dict[str, Any]] = None
