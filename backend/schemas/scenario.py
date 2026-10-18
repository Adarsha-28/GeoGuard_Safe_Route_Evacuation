"""Pydantic v2 schemas for GeoGuard V6 Scenario Simulation and Resilience."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ScenarioSimulateRequest(BaseModel):
    """Request payload to initiate a flood scenario simulation."""

    name: str = Field(..., min_length=1, max_length=100, description="Name of the scenario")
    rainfall_multiplier: float = Field(
        1.25,
        ge=0.1,
        le=10.0,
        description="Rainfall stress multiplier (e.g., 1.25 for +25%, 1.5 for +50%, 2.0 for +100%)",
    )
    horizon: str = Field("nowcast", description="Forecast horizon: nowcast, 6h, 12h, or 24h")
    simulation_demand_factor: float = Field(
        1.0,
        ge=0.1,
        le=5.0,
        description="Evacuation demand multiplier on shelter capacity: 1.0x, 1.25x, 1.5x, 2.0x",
    )
    description: str | None = Field(None, max_length=500, description="Optional scenario description")
    operator: str = Field("Command Center Operator", max_length=100, description="Name or identifier of operator")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "+50% Monsoon Surge Stress Test",
                "rainfall_multiplier": 1.5,
                "horizon": "6h",
                "simulation_demand_factor": 1.25,
                "description": "Stress testing Adyar and Cooum catchment areas under 1.5x precipitation",
                "operator": "Disaster Response Unit",
            }
        }
    )


class ScenarioResilienceSubscores(BaseModel):
    overall: float
    shelter: float
    route: float
    data: float
    model: float
    operational: float


class ScenarioSummaryResponse(BaseModel):
    id: str
    name: str
    description: str | None
    rainfall_multiplier: float
    horizon: str
    simulation_demand_factor: float
    baseline_rainfall_mm: float
    simulated_rainfall_mm: float
    total_sectors: int
    sectors_deteriorated: int
    sectors_improved: int
    sectors_critical: int
    sectors_high: int
    shelters_stressed: int
    shelters_overloaded: int
    routes_unsafe: int
    routes_blocked: int
    resilience: ScenarioResilienceSubscores
    model_version: str
    is_fallback: bool
    execution_duration_ms: float
    disclaimer: str
    created_at: str | None


class ScenarioSectorResponse(BaseModel):
    id: int
    scenario_id: str
    grid_id: int
    grid_name: str
    baseline_probability: float
    simulated_probability: float
    probability_delta: float
    baseline_risk: str
    simulated_risk: str
    risk_transition: str
    is_transitioned: bool
    spatial_propagation_type: str
    priority_score: float
    priority_rank: int
    priority_category: str
    features: dict[str, Any]
    created_at: str | None


class ScenarioShelterResponse(BaseModel):
    id: int
    scenario_id: str
    shelter_id: int
    shelter_name: str
    total_capacity: int
    current_available_capacity: int
    simulation_demand_factor: float
    simulated_demand: int
    remaining_simulated_capacity: int
    stress_status: str
    surrounding_flood_risk: str
    suitability_score: float
    alternative_shelter_id: int | None
    alternative_shelter_name: str | None
    created_at: str | None


class ScenarioRouteResponse(BaseModel):
    id: int
    scenario_id: str
    origin_grid_id: int
    origin_grid_name: str | None
    destination_shelter_id: int
    destination_shelter_name: str | None
    route_role: str
    distance_km: float
    duration_min: float
    baseline_hazard_score: float
    simulated_hazard_score: float
    simulated_peak_risk: str
    high_risk_exposure_pct: float
    severe_risk_exposure_pct: float
    route_status: str
    advisory_message: str
    created_at: str | None


class ResilienceResponse(BaseModel):
    overall_resilience_score: float
    category: str
    subscores: dict[str, float]
    formula_breakdown: dict[str, Any]
    weights: dict[str, float]
    formula: str


class FailureTestRequest(BaseModel):
    simulation_type: str = Field(
        ...,
        description="Failure mode to simulate: WEATHER_API_UNAVAILABLE, WEATHER_DATA_STALE, ML_MODEL_UNAVAILABLE, DATABASE_UNAVAILABLE, OSRM_UNAVAILABLE, SCHEDULER_FAILURE",
    )


class FailureTestResponse(BaseModel):
    simulation_type: str
    detected: bool
    fallback_activated: bool
    fallback_type: str
    degraded_status: str
    response_time_ms: float
    audit_record_created: bool
    details: dict[str, Any]
    record_id: int | None


class DecisionLogEntryResponse(BaseModel):
    id: int
    scenario_id: str | None
    event_type: str
    operator: str
    action_taken: str
    parameters: dict[str, Any]
    impact_summary: dict[str, Any]
    timestamp: str | None
