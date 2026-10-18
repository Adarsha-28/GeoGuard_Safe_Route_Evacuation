"""FastAPI router for Near-Real-Time Operational Intelligence Status and Control."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.operations import OperationalCycleTriggerResponse, OperationsStatusResponse
from backend.services.operational_scheduler import get_operational_scheduler

router = APIRouter(prefix="/api/operations", tags=["Operations"])


@router.get("/status", response_model=OperationsStatusResponse)
def get_operational_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retrieve verified operational status of live weather, ML inference, and alert systems."""
    scheduler = get_operational_scheduler()
    return scheduler.get_operational_status(db)


@router.post("/run-cycle", response_model=OperationalCycleTriggerResponse)
def trigger_operational_cycle(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Trigger an on-demand operational intelligence cycle under concurrency lock."""
    scheduler = get_operational_scheduler()
    return scheduler.run_single_cycle(db, trigger_type="manual")
