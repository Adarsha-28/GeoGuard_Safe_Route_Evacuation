"""FastAPI router for Emergency Alerts."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.alert import (
    AlertAcknowledgeResponse,
    AlertCreate,
    AlertCreateResponse,
    AlertResponse,
)
from backend.services.alert_service import get_alert_service

router = APIRouter(tags=["Alerts"])


@router.get("/api/alerts", response_model=list[AlertResponse])
@router.get("/api/alerts/all", response_model=list[AlertResponse], include_in_schema=False)
def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    active_only: bool = Query(False),
    severity: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve emergency alerts with optional filtering by severity and active state."""
    alert_service = get_alert_service()
    return alert_service.get_all_alerts(db, limit=limit, active_only=active_only, severity=severity)


@router.get("/api/alerts/active", response_model=list[AlertResponse])
def get_active_alerts(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve only currently active operational alerts."""
    alert_service = get_alert_service()
    return alert_service.get_all_alerts(db, limit=limit, active_only=True)


@router.get("/api/alerts/{alert_id}", response_model=AlertResponse)
def get_alert_by_id(alert_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retrieve a specific emergency alert by primary key."""
    alert_service = get_alert_service()
    alert = alert_service.get_alert_by_id(db, alert_id=alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")
    return alert


@router.post("/api/alerts/{alert_id}/acknowledge", response_model=AlertAcknowledgeResponse)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)) -> AlertAcknowledgeResponse:
    """Acknowledge an emergency alert and deactivate its broadcasting status."""
    alert_service = get_alert_service()
    updated = alert_service.acknowledge_alert(db, alert_id=alert_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")
    return AlertAcknowledgeResponse(
        message=f"Alert {alert_id} acknowledged and deactivated.",
        alert=AlertResponse(**updated),
    )


@router.post("/api/alerts", response_model=AlertCreateResponse, status_code=201)
@router.post("/api/alerts/create", response_model=AlertCreateResponse, status_code=201, include_in_schema=False)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)) -> AlertCreateResponse:
    """Publish a new administrative emergency alert bulletin."""
    alert_service = get_alert_service()
    try:
        new_alert = alert_service.create_alert(
            db=db,
            title=payload.title,
            severity=payload.severity,
            zone=payload.zone,
            message=payload.message,
        )
        return AlertCreateResponse(
            message="Alert published successfully.",
            alert=AlertResponse(**new_alert),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to persist alert: {e}")
