"""API Endpoint for Operational Zone Prioritization."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.v5_intelligence import ZonePriorityResponse
from backend.services.forecast_service import VALID_HORIZONS
from backend.services.priority_service import get_priority_service

router = APIRouter(prefix="/api/priorities", tags=["V5 Operational Prioritization"])


@router.get(
    "",
    response_model=ZonePriorityResponse,
    summary="Get triage prioritization ranking across Chennai sectors",
)
def get_zone_priorities(
    horizon: str = Query("nowcast", description="Operational horizon: nowcast, 6h, 12h, 24h"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level: Low, Moderate, High, Severe"),
    category: Optional[str] = Query(None, description="Filter by priority category: Critical, High, Medium, Low"),
    db: Session = Depends(get_db),
):
    """Retrieve prioritized sector scores based on flood probability, deterioration, rainfall, and shelter access."""
    norm_horizon = horizon.lower().strip()
    if norm_horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid horizon '{horizon}'. Must be one of {list(VALID_HORIZONS)}.",
        )

    service = get_priority_service()
    try:
        priorities = service.calculate_priorities(db=db, horizon=norm_horizon, persist=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Priority calculation failed: {e}")

    # Filtering
    if risk_level:
        priorities = [p for p in priorities if p["risk_level"].lower() == risk_level.lower().strip()]
    if category:
        priorities = [p for p in priorities if p["priority_category"].lower() == category.lower().strip()]

    crit_cnt = sum(1 for p in priorities if p["priority_category"] == "Critical")
    high_cnt = sum(1 for p in priorities if p["priority_category"] == "High")
    med_cnt = sum(1 for p in priorities if p["priority_category"] == "Medium")
    low_cnt = sum(1 for p in priorities if p["priority_category"] == "Low")

    return {
        "total_zones": len(priorities),
        "horizon": norm_horizon,
        "critical_count": crit_cnt,
        "high_count": high_cnt,
        "medium_count": med_cnt,
        "low_count": low_cnt,
        "priorities": priorities,
    }
