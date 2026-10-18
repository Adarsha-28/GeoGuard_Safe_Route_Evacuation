"""API Endpoints for Shelter and Route Intelligence."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.v5_intelligence import RouteIntelligenceResponse, ShelterIntelligenceResponse
from backend.services.route_intelligence_service import get_route_intelligence_service
from backend.services.shelter_intelligence_service import get_shelter_intelligence_service

router = APIRouter(prefix="/api", tags=["V5 Shelter & Route Intelligence"])


@router.get(
    "/shelters/intelligence",
    response_model=ShelterIntelligenceResponse,
    summary="Get operational shelter suitability, capacity utilization, and surrounding flood risks",
)
def get_shelter_intelligence(
    lat: Optional[float] = Query(None, description="Optional user/incident latitude"),
    lng: Optional[float] = Query(None, description="Optional user/incident longitude"),
    radius_km: float = Query(30.0, ge=1.0, le=100.0, description="Spatial search radius in km"),
    db: Session = Depends(get_db),
):
    """Assess active relief shelters for operational suitability, capacity headroom, and surrounding hazard."""
    service = get_shelter_intelligence_service()
    try:
        shelters = service.evaluate_shelters_intelligence(
            db=db,
            user_lat=lat,
            user_lng=lng,
            radius_km=radius_km,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shelter intelligence evaluation failed: {e}")

    opt_cnt = sum(1 for s in shelters if s["warning_status"] == "Optimal")
    elev_cnt = sum(1 for s in shelters if s["warning_status"] in ("Surrounding Risk Elevated", "Severe Risk Zone"))
    cap_cnt = sum(1 for s in shelters if s["warning_status"] == "At Capacity")

    return {
        "total_shelters": len(shelters),
        "optimal_count": opt_cnt,
        "elevated_risk_count": elev_cnt,
        "at_capacity_count": cap_cnt,
        "shelters": shelters,
    }


@router.get(
    "/routes/intelligence",
    response_model=RouteIntelligenceResponse,
    summary="Evaluate candidate evacuation route hazard exposure and safety status",
)
def get_route_intelligence(
    src_lat: float = Query(..., description="Origin latitude coordinate"),
    src_lng: float = Query(..., description="Origin longitude coordinate"),
    shelter_id: int = Query(..., description="Target shelter ID"),
    db: Session = Depends(get_db),
):
    """Evaluate candidate evacuation route along OSRM driving geometry with advisory flood hazard metrics."""
    service = get_route_intelligence_service()
    try:
        data = service.evaluate_route_intelligence(
            db=db,
            src_lat=src_lat,
            src_lng=src_lng,
            shelter_id=shelter_id,
        )
        return data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route intelligence evaluation error: {e}")
