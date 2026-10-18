"""FastAPI router for Relief Shelters and PostGIS Spatial Search."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.shelter import ShelterResponse
from backend.services.shelter_service import get_shelter_service, validate_coordinates

router = APIRouter(tags=["Shelters"])


@router.get("/api/shelters", response_model=list[ShelterResponse])
@router.get("/api/shelters/all", response_model=list[ShelterResponse], include_in_schema=False)
def get_all_shelters(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Retrieve all active relief shelters."""
    shelter_service = get_shelter_service()
    return shelter_service.get_all_shelters(db, active_only=True)


@router.get("/api/shelters/nearby", response_model=list[ShelterResponse])
def get_nearby_shelters(
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    radius: float = Query(25.0, ge=0.1, le=100.0, description="Search radius in km"),
    limit: int = Query(10, ge=1, le=50, description="Max shelters to return"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Search for nearby relief shelters using database-side PostGIS spatial queries."""
    is_valid, err = validate_coordinates(lat, lng)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err)

    shelter_service = get_shelter_service()
    try:
        return shelter_service.find_nearby_shelters(
            db=db,
            lat=lat,
            lng=lng,
            radius_km=radius,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query nearby shelters: {e}")


@router.get("/api/shelters/{shelter_id}", response_model=ShelterResponse)
def get_shelter_by_id(shelter_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retrieve single relief shelter details by ID."""
    shelter_service = get_shelter_service()
    shelter = shelter_service.get_shelter(db, shelter_id)
    if not shelter:
        raise HTTPException(status_code=404, detail=f"Shelter with ID {shelter_id} not found.")
    return shelter
