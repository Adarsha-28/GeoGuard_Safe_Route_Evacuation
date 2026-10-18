"""API Endpoint for Command Center Operational Event Timeline."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.v5_intelligence import TimelineResponse
from backend.services.timeline_service import TimelineService

router = APIRouter(prefix="/api/operations", tags=["V5 Operational Timeline"])


@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Get chronological event ledger for command center operators",
)
def get_operational_timeline(
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    grid_id: Optional[int] = Query(None, description="Filter by affected grid ID"),
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
    db: Session = Depends(get_db),
):
    """Retrieve operational event timeline including weather syncs, prediction cycles, alerts, and state transitions."""
    events = TimelineService.get_timeline(
        db=db,
        hours=hours,
        event_type=event_type,
        grid_id=grid_id,
        limit=limit,
    )
    return {
        "total_events": len(events),
        "query_window_hours": hours,
        "events": events,
    }
