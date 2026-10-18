"""API Endpoints for Multi-Horizon Forecasts and Historical Prediction Tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.models.prediction_history import PredictionHistory
from backend.schemas.v5_intelligence import ForecastResponse, RiskTrendHistoryItem
from backend.services.forecast_service import VALID_HORIZONS, get_forecast_service

router = APIRouter(prefix="/api/predictions", tags=["V5 Predictive Intelligence"])


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Get multi-horizon flood risk predictions across Chennai sectors",
)
def get_flood_forecast(
    horizon: str = Query("nowcast", description="Operational horizon: nowcast, 6h, 12h, 24h"),
    grid_id: Optional[int] = Query(None, description="Optional single grid ID filter"),
    db: Session = Depends(get_db),
):
    """Retrieve operational predictions and model-supported feature attributions for a designated horizon."""
    norm_horizon = horizon.lower().strip()
    if norm_horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid horizon '{horizon}'. Must be one of {list(VALID_HORIZONS)}.",
        )

    service = get_forecast_service()
    try:
        predictions = service.predict_for_horizon(db=db, horizon=norm_horizon, grid_id=grid_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast inference error: {e}")

    active_model = service.ml_service.model_version
    return {
        "horizon": norm_horizon,
        "total_grids": len(predictions),
        "active_model": active_model,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "predictions": predictions,
    }


@router.get(
    "/history/{grid_id}",
    response_model=list[RiskTrendHistoryItem],
    summary="Retrieve prediction audit history for a specific grid sector",
)
def get_prediction_history_by_grid(
    grid_id: int,
    horizon: str = Query("nowcast", description="Operational horizon filter"),
    limit: int = Query(50, ge=1, le=200, description="Max history records to return"),
    db: Session = Depends(get_db),
):
    """Retrieve persisted prediction history records for auditing and verification."""
    records = (
        db.query(PredictionHistory)
        .filter(
            PredictionHistory.grid_id == grid_id,
            PredictionHistory.horizon == horizon.lower().strip(),
        )
        .order_by(PredictionHistory.predicted_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in records]
