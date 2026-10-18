"""FastAPI router for Geospatial Risk Grids."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.services.risk_service import get_risk_service

router = APIRouter(tags=["Grids"])


@router.get("/api/grids")
def get_grids(
    model: str = Query("ml", description="Prediction model engine: 'ml' or 'deterministic'"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve all monitored Chennai flood-risk zones as GeoJSON FeatureCollection."""
    risk_service = get_risk_service()
    return risk_service.get_all_grids(db, model=model)


@router.get("/api/grids/{grid_id}")
def get_grid_by_id(grid_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retrieve specific grid sector feature by integer ID."""
    risk_service = get_risk_service()
    grid = risk_service.get_grid_by_id(db, grid_id)
    if not grid:
        raise HTTPException(status_code=404, detail=f"Grid with ID {grid_id} not found.")
    return grid
