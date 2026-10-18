"""SQLAlchemy models for GeoGuard V6 Scenario Simulation, Adaptive Evacuation & Resilience."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from backend.database.base import Base


class Scenario(Base):
    """Master record for a simulated flood stress scenario."""

    __tablename__ = "scenarios"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    rainfall_multiplier = Column(Float, nullable=False, server_default="1.0")
    horizon = Column(String(20), nullable=False, server_default="nowcast")
    simulation_demand_factor = Column(Float, nullable=False, server_default="1.0")
    baseline_rainfall_mm = Column(Float, nullable=False, server_default="0.0")
    simulated_rainfall_mm = Column(Float, nullable=False, server_default="0.0")
    total_sectors = Column(Integer, nullable=False, server_default="34")
    sectors_deteriorated = Column(Integer, nullable=False, server_default="0")
    sectors_improved = Column(Integer, nullable=False, server_default="0")
    sectors_critical = Column(Integer, nullable=False, server_default="0")
    sectors_high = Column(Integer, nullable=False, server_default="0")
    shelters_stressed = Column(Integer, nullable=False, server_default="0")
    shelters_overloaded = Column(Integer, nullable=False, server_default="0")
    routes_unsafe = Column(Integer, nullable=False, server_default="0")
    routes_blocked = Column(Integer, nullable=False, server_default="0")
    system_resilience_score = Column(Float, nullable=False, server_default="100.0")
    shelter_resilience_score = Column(Float, nullable=False, server_default="100.0")
    route_resilience_score = Column(Float, nullable=False, server_default="100.0")
    data_resilience_score = Column(Float, nullable=False, server_default="100.0")
    model_resilience_score = Column(Float, nullable=False, server_default="100.0")
    operational_resilience_score = Column(Float, nullable=False, server_default="100.0")
    model_version = Column(String(50), nullable=False, server_default="v5.0.0")
    is_fallback = Column(Boolean, nullable=False, server_default="false")
    execution_duration_ms = Column(Float, nullable=False, server_default="0.0")
    disclaimer = Column(
        String(200),
        nullable=False,
        server_default="SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA",
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    sector_results = relationship("ScenarioSectorResult", back_populates="scenario", cascade="all, delete-orphan")
    shelter_results = relationship("ScenarioShelterResult", back_populates="scenario", cascade="all, delete-orphan")
    route_results = relationship("ScenarioRouteResult", back_populates="scenario", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rainfall_multiplier": round(self.rainfall_multiplier, 2),
            "horizon": self.horizon,
            "simulation_demand_factor": round(self.simulation_demand_factor, 2),
            "baseline_rainfall_mm": round(self.baseline_rainfall_mm, 2),
            "simulated_rainfall_mm": round(self.simulated_rainfall_mm, 2),
            "total_sectors": self.total_sectors,
            "sectors_deteriorated": self.sectors_deteriorated,
            "sectors_improved": self.sectors_improved,
            "sectors_critical": self.sectors_critical,
            "sectors_high": self.sectors_high,
            "shelters_stressed": self.shelters_stressed,
            "shelters_overloaded": self.shelters_overloaded,
            "routes_unsafe": self.routes_unsafe,
            "routes_blocked": self.routes_blocked,
            "resilience": {
                "overall": round(self.system_resilience_score, 1),
                "shelter": round(self.shelter_resilience_score, 1),
                "route": round(self.route_resilience_score, 1),
                "data": round(self.data_resilience_score, 1),
                "model": round(self.model_resilience_score, 1),
                "operational": round(self.operational_resilience_score, 1),
            },
            "model_version": self.model_version,
            "is_fallback": self.is_fallback,
            "execution_duration_ms": round(self.execution_duration_ms, 2),
            "disclaimer": self.disclaimer,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScenarioSectorResult(Base):
    """Sector-level comparative flood risk prediction under a simulated scenario."""

    __tablename__ = "scenario_sector_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False, index=True)
    grid_name = Column(String(100), nullable=False)
    baseline_probability = Column(Float, nullable=False)
    simulated_probability = Column(Float, nullable=False)
    probability_delta = Column(Float, nullable=False)
    baseline_risk = Column(String(20), nullable=False)
    simulated_risk = Column(String(20), nullable=False)
    risk_transition = Column(String(50), nullable=False)
    is_transitioned = Column(Boolean, nullable=False, server_default="false")
    spatial_propagation_type = Column(String(20), nullable=False, server_default="UNAFFECTED")
    priority_score = Column(Float, nullable=False, server_default="0.0")
    priority_rank = Column(Integer, nullable=False, server_default="0")
    priority_category = Column(String(20), nullable=False, server_default="Low")
    features_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    scenario = relationship("Scenario", back_populates="sector_results")
    grid = relationship("Grid")

    __table_args__ = (
        Index("idx_scen_sec_scen_grid", "scenario_id", "grid_id"),
        Index("idx_scen_sec_risk", "simulated_risk"),
    )

    def to_dict(self) -> dict[str, Any]:
        features = {}
        if self.features_json:
            try:
                features = json.loads(self.features_json)
            except Exception:
                features = {}
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "grid_id": self.grid_id,
            "grid_name": self.grid_name,
            "baseline_probability": round(self.baseline_probability, 4),
            "simulated_probability": round(self.simulated_probability, 4),
            "probability_delta": round(self.probability_delta, 4),
            "baseline_risk": self.baseline_risk,
            "simulated_risk": self.simulated_risk,
            "risk_transition": self.risk_transition,
            "is_transitioned": self.is_transitioned,
            "spatial_propagation_type": self.spatial_propagation_type,
            "priority_score": round(self.priority_score, 4),
            "priority_rank": self.priority_rank,
            "priority_category": self.priority_category,
            "features": features,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScenarioShelterResult(Base):
    """Shelter capacity stress assessment under a simulated scenario."""

    __tablename__ = "scenario_shelter_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="CASCADE"), nullable=False, index=True)
    shelter_name = Column(String(150), nullable=False)
    total_capacity = Column(Integer, nullable=False)
    current_available_capacity = Column(Integer, nullable=False)
    simulation_demand_factor = Column(Float, nullable=False, server_default="1.0")
    simulated_demand = Column(Integer, nullable=False, server_default="0")
    remaining_simulated_capacity = Column(Integer, nullable=False)
    stress_status = Column(String(20), nullable=False, server_default="NORMAL")  # NORMAL, STRESSED, OVERLOADED
    surrounding_flood_risk = Column(String(20), nullable=False, server_default="Low")
    suitability_score = Column(Float, nullable=False, server_default="1.0")
    alternative_shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    scenario = relationship("Scenario", back_populates="shelter_results")
    shelter = relationship("Shelter", foreign_keys=[shelter_id])
    alternative_shelter = relationship("Shelter", foreign_keys=[alternative_shelter_id])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "shelter_id": self.shelter_id,
            "shelter_name": self.shelter_name,
            "total_capacity": self.total_capacity,
            "current_available_capacity": self.current_available_capacity,
            "simulation_demand_factor": round(self.simulation_demand_factor, 2),
            "simulated_demand": self.simulated_demand,
            "remaining_simulated_capacity": self.remaining_simulated_capacity,
            "stress_status": self.stress_status,
            "surrounding_flood_risk": self.surrounding_flood_risk,
            "suitability_score": round(self.suitability_score, 3),
            "alternative_shelter_id": self.alternative_shelter_id,
            "alternative_shelter_name": self.alternative_shelter.name if self.alternative_shelter else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScenarioRouteResult(Base):
    """Multi-path evacuation route evaluation under a simulated scenario."""

    __tablename__ = "scenario_route_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    origin_grid_id = Column(Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="CASCADE"), nullable=False, index=True)
    route_role = Column(String(20), nullable=False, server_default="PRIMARY")  # PRIMARY, ALTERNATIVE_1, ALTERNATIVE_2
    distance_km = Column(Float, nullable=False, server_default="0.0")
    duration_min = Column(Float, nullable=False, server_default="0.0")
    baseline_hazard_score = Column(Float, nullable=False, server_default="0.0")
    simulated_hazard_score = Column(Float, nullable=False, server_default="0.0")
    simulated_peak_risk = Column(String(20), nullable=False, server_default="Low")
    high_risk_exposure_pct = Column(Float, nullable=False, server_default="0.0")
    severe_risk_exposure_pct = Column(Float, nullable=False, server_default="0.0")
    route_status = Column(
        String(30),
        nullable=False,
        server_default="AVAILABLE",  # AVAILABLE, CAUTION, UNSAFE, BLOCKED_BY_SIMULATION
    )
    advisory_message = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    scenario = relationship("Scenario", back_populates="route_results")
    origin_grid = relationship("Grid")
    destination_shelter = relationship("Shelter")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "origin_grid_id": self.origin_grid_id,
            "origin_grid_name": self.origin_grid.name if self.origin_grid else None,
            "destination_shelter_id": self.destination_shelter_id,
            "destination_shelter_name": self.destination_shelter.name if self.destination_shelter else None,
            "route_role": self.route_role,
            "distance_km": round(self.distance_km, 2),
            "duration_min": round(self.duration_min, 1),
            "baseline_hazard_score": round(self.baseline_hazard_score, 4),
            "simulated_hazard_score": round(self.simulated_hazard_score, 4),
            "simulated_peak_risk": self.simulated_peak_risk,
            "high_risk_exposure_pct": round(self.high_risk_exposure_pct, 1),
            "severe_risk_exposure_pct": round(self.severe_risk_exposure_pct, 1),
            "route_status": self.route_status,
            "advisory_message": self.advisory_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ResilienceAssessment(Base):
    """System and component resilience assessment."""

    __tablename__ = "resilience_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True, index=True)
    overall_resilience_score = Column(Float, nullable=False)
    shelter_resilience_score = Column(Float, nullable=False)
    route_resilience_score = Column(Float, nullable=False)
    data_resilience_score = Column(Float, nullable=False)
    model_resilience_score = Column(Float, nullable=False)
    operational_resilience_score = Column(Float, nullable=False)
    formula_version = Column(String(50), nullable=False, server_default="v6.0.0")
    details_json = Column(Text, nullable=True)
    assessed_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    def to_dict(self) -> dict[str, Any]:
        details = {}
        if self.details_json:
            try:
                details = json.loads(self.details_json)
            except Exception:
                details = {}
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "overall_resilience_score": round(self.overall_resilience_score, 1),
            "subscores": {
                "shelter": round(self.shelter_resilience_score, 1),
                "route": round(self.route_resilience_score, 1),
                "data": round(self.data_resilience_score, 1),
                "model": round(self.model_resilience_score, 1),
                "operational": round(self.operational_resilience_score, 1),
            },
            "formula_version": self.formula_version,
            "details": details,
            "assessed_at": self.assessed_at.isoformat() if self.assessed_at else None,
        }


class FailureSimulation(Base):
    """Audit log of controlled resilience failure simulations."""

    __tablename__ = "failure_simulations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_type = Column(String(50), nullable=False, index=True)
    triggered_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    detected = Column(Boolean, nullable=False)
    fallback_activated = Column(Boolean, nullable=False)
    fallback_type = Column(String(100), nullable=False)
    degraded_status = Column(String(50), nullable=False)
    response_time_ms = Column(Float, nullable=False, server_default="0.0")
    audit_record_created = Column(Boolean, nullable=False, server_default="true")
    details_json = Column(Text, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        details = {}
        if self.details_json:
            try:
                details = json.loads(self.details_json)
            except Exception:
                details = {}
        return {
            "id": self.id,
            "simulation_type": self.simulation_type,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "detected": self.detected,
            "fallback_activated": self.fallback_activated,
            "fallback_type": self.fallback_type,
            "degraded_status": self.degraded_status,
            "response_time_ms": round(self.response_time_ms, 2),
            "audit_record_created": self.audit_record_created,
            "details": details,
        }


class DecisionAuditLog(Base):
    """Reproducible audit trail for operational decisions, scenarios, and simulations."""

    __tablename__ = "decision_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    operator = Column(String(50), nullable=False, server_default="Command Center Operator")
    action_taken = Column(String(200), nullable=False)
    parameters_json = Column(Text, nullable=True)
    impact_summary_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    def to_dict(self) -> dict[str, Any]:
        params = {}
        impact = {}
        if self.parameters_json:
            try:
                params = json.loads(self.parameters_json)
            except Exception:
                params = {}
        if self.impact_summary_json:
            try:
                impact = json.loads(self.impact_summary_json)
            except Exception:
                impact = {}
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "event_type": self.event_type,
            "operator": self.operator,
            "action_taken": self.action_taken,
            "parameters": params,
            "impact_summary": impact,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
