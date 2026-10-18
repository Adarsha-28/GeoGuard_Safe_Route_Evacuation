"""FastAPI router for Safe Evacuation Routing and Initiation."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.route import EvacuationStartRequest, RouteRequest, RouteResponse
from backend.services.routing_service import get_routing_service
from backend.services.shelter_service import get_shelter_service

router = APIRouter(tags=["Routes"])


@router.post("/api/routes/safe", response_model=RouteResponse)
@router.post("/api/routes", response_model=RouteResponse, include_in_schema=False)
@router.post("/api/routes/recalculate", response_model=RouteResponse, include_in_schema=False)
def calculate_safe_route(payload: RouteRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Calculate safest evacuation route to accessible shelters avoiding severe flood hazard."""
    routing_service = get_routing_service()
    try:
        return routing_service.calculate_safest_evacuation_route(
            db=db,
            lat=payload.latitude,
            lng=payload.longitude,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Routing service encountered an unexpected error.")


@router.post("/api/evacuation/start")
def start_evacuation(payload: EvacuationStartRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Acknowledge evacuation initiation and atomically update shelter capacity."""
    shelter_service = get_shelter_service()
    success, result = shelter_service.decrement_shelter_capacity(db, payload.shelter_id)

    if not success:
        raise HTTPException(status_code=400, detail=str(result))

    return {
        "message": "Evacuation route activated. Shelter capacity updated.",
        "shelter": result,
    }
