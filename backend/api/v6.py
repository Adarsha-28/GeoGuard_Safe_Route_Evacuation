"""FastAPI Router for GeoGuard V6 Scenario Simulation, Adaptive Evacuation & Resilience."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.models.scenario import (
    DecisionAuditLog,
    Scenario,
    ScenarioRouteResult,
    ScenarioSectorResult,
    ScenarioShelterResult,
)
from backend.schemas.scenario import (
    DecisionLogEntryResponse,
    FailureTestRequest,
    FailureTestResponse,
    ResilienceResponse,
    ScenarioRouteResponse,
    ScenarioSectorResponse,
    ScenarioShelterResponse,
    ScenarioSimulateRequest,
    ScenarioSummaryResponse,
)
from backend.services.failure_simulation_service import get_failure_simulation_service
from backend.services.resilience_scoring_service import get_resilience_scoring_service
from backend.services.scenario_simulation_service import get_scenario_simulation_service

router = APIRouter(prefix="/api/v6", tags=["V6 Scenario Simulation & Resilience"])


@router.post("/scenarios/simulate", response_model=dict[str, Any])
def simulate_scenario(
    req: ScenarioSimulateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute a multi-horizon rainfall stress scenario without retraining the ML model."""
    service = get_scenario_simulation_service()
    try:
        result = service.simulate(
            db=db,
            name=req.name,
            rainfall_multiplier=req.rainfall_multiplier,
            horizon=req.horizon,
            simulation_demand_factor=req.simulation_demand_factor,
            description=req.description,
            operator=req.operator,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")


@router.get("/scenarios", response_model=list[ScenarioSummaryResponse])
def list_scenarios(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List historical simulated flood scenarios."""
    scenarios = (
        db.query(Scenario)
        .order_by(Scenario.created_at.desc())
        .limit(limit)
        .all()
    )
    return [s.to_dict() for s in scenarios]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioSummaryResponse)
def get_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve detailed metadata and metrics for a specific scenario."""
    scen = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scen:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")
    return scen.to_dict()


@router.get("/scenarios/{scenario_id}/sectors", response_model=list[ScenarioSectorResponse])
def get_scenario_sectors(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve sector-by-sector comparative risk, probability deltas, and spatial propagation."""
    scen = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scen:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    sectors = (
        db.query(ScenarioSectorResult)
        .filter(ScenarioSectorResult.scenario_id == scenario_id)
        .order_by(ScenarioSectorResult.priority_rank.asc())
        .all()
    )
    return [s.to_dict() for s in sectors]


@router.get("/scenarios/{scenario_id}/shelters", response_model=list[ScenarioShelterResponse])
def get_scenario_shelters(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve shelter capacity stress analysis, headroom status, and alternatives."""
    scen = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scen:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    shelters = (
        db.query(ScenarioShelterResult)
        .filter(ScenarioShelterResult.scenario_id == scenario_id)
        .order_by(ScenarioShelterResult.suitability_score.asc())
        .all()
    )
    return [s.to_dict() for s in shelters]


@router.get("/scenarios/{scenario_id}/routes", response_model=list[ScenarioRouteResponse])
def get_scenario_routes(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve multi-path evacuation routes (Primary, Alt 1, Alt 2) with status and hazard exposure."""
    scen = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scen:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    routes = (
        db.query(ScenarioRouteResult)
        .filter(ScenarioRouteResult.scenario_id == scenario_id)
        .order_by(ScenarioRouteResult.simulated_hazard_score.desc())
        .all()
    )
    return [r.to_dict() for r in routes]


@router.get("/scenarios/{scenario_id}/compare")
def compare_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve side-by-side comparative summary between baseline and simulated scenario."""
    scen = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scen:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    sectors = db.query(ScenarioSectorResult).filter(ScenarioSectorResult.scenario_id == scenario_id).all()
    shelters = db.query(ScenarioShelterResult).filter(ScenarioShelterResult.scenario_id == scenario_id).all()

    baseline_critical = sum(1 for s in sectors if s.baseline_risk in ("High", "Severe"))
    simulated_critical = sum(1 for s in sectors if s.simulated_risk in ("High", "Severe"))
    deteriorated_count = scen.sectors_deteriorated

    resilience_service = get_resilience_scoring_service()
    baseline_res = resilience_service.compute_resilience(db)
    sim_res = resilience_service.compute_resilience(
        db,
        shelter_stress_results=[s.to_dict() for s in shelters],
    )

    return {
        "scenario": scen.to_dict(),
        "comparison_metrics": {
            "baseline_critical_sectors": baseline_critical,
            "simulated_critical_sectors": simulated_critical,
            "deteriorated_sectors": deteriorated_count,
            "total_sectors": len(sectors),
            "baseline_resilience_score": baseline_res.overall,
            "simulated_resilience_score": sim_res.overall,
            "resilience_delta": round(sim_res.overall - baseline_res.overall, 1),
            "shelters_overloaded": sum(1 for s in shelters if s.stress_status == "OVERLOADED"),
            "shelters_stressed": sum(1 for s in shelters if s.stress_status == "STRESSED"),
        },
        "disclaimer": "SIMULATED SCENARIO \u2014 NOT OBSERVED FLOOD DATA",
    }


@router.get("/resilience", response_model=ResilienceResponse)
def get_resilience_assessment(
    scenario_id: str | None = Query(None, description="Optional scenario ID for simulated assessment"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve live baseline or scenario-specific 5-component resilience score."""
    resilience_service = get_resilience_scoring_service()
    shelter_stress = None
    route_results = None

    if scenario_id:
        shelter_recs = (
            db.query(ScenarioShelterResult)
            .filter(ScenarioShelterResult.scenario_id == scenario_id)
            .all()
        )
        shelter_stress = [s.to_dict() for s in shelter_recs]

        route_recs = (
            db.query(ScenarioRouteResult)
            .filter(ScenarioRouteResult.scenario_id == scenario_id)
            .all()
        )
        route_results = [r.to_dict() for r in route_recs]

    result = resilience_service.compute_resilience(
        db=db,
        shelter_stress_results=shelter_stress,
        route_results=route_results,
    )
    return result.to_dict()


@router.post("/resilience/failure-test", response_model=FailureTestResponse)
def trigger_failure_simulation(
    req: FailureTestRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute a controlled test double failure simulation and verify fallback activation."""
    service = get_failure_simulation_service()
    try:
        return service.execute_failure_test(db, req.simulation_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failure simulation error: {e}")


@router.get("/decision-log", response_model=list[DecisionLogEntryResponse])
def get_decision_audit_log(
    limit: int = Query(50, ge=1, le=200),
    event_type: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve chronological operational decision and scenario audit log."""
    query = db.query(DecisionAuditLog)
    if event_type:
        query = query.filter(DecisionAuditLog.event_type == event_type)
    entries = query.order_by(DecisionAuditLog.timestamp.desc()).limit(limit).all()
    return [e.to_dict() for e in entries]
