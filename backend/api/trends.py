"""API Endpoint for Temporal Risk Trends and Deterioration Analysis."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.v5_intelligence import RiskTrendResponse
from backend.services.forecast_service import VALID_HORIZONS
from backend.services.risk_trend_service import get_risk_trend_service

router = APIRouter(prefix="/api/risk", tags=["V5 Risk Trends"])


@router.get(
    "/trends/{grid_id}",
    response_model=RiskTrendResponse,
    summary="Get temporal flood risk evolution and trend detection for a grid sector",
)
def get_grid_risk_trends(
    grid_id: int,
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    horizon: str = Query("nowcast", description="Prediction horizon: nowcast, 6h, 12h, 24h"),
    db: Session = Depends(get_db),
):
    """Retrieve historical risk telemetry, probability evolution, and directional trend classification."""
    norm_horizon = horizon.lower().strip()
    if norm_horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid horizon '{horizon}'. Must be one of {list(VALID_HORIZONS)}.",
        )

    service = get_risk_trend_service()
    try:
        data = service.get_grid_risk_trends(db=db, grid_id=grid_id, hours=hours, horizon=norm_horizon)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query risk trends: {e}")
