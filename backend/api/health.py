"""FastAPI router for System Health Check."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.connection import check_db_connection, get_db
from backend.schemas.health import HealthResponse
from backend.services.risk_service import get_risk_service

router = APIRouter(tags=["Health"])


@router.get("/api/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    """Check system operational status and database connectivity."""
    is_connected, db_status = check_db_connection()
    risk_service = get_risk_service()
    telemetry = risk_service.get_telemetry_summary(db)

    from backend.services.ml_prediction_service import get_ml_prediction_service
    from backend.services.operational_scheduler import get_operational_scheduler
    from backend.services.weather_ingestion_service import get_weather_ingestion_service

    ml_service = get_ml_prediction_service()
    weather_service = get_weather_ingestion_service()
    scheduler = get_operational_scheduler()

    db_health = "healthy" if is_connected else "unavailable"
    weather_health = weather_service.last_sync_status if weather_service.last_sync_status != "initialized" else "healthy"
    ml_health = "healthy" if ml_service.is_available else "degraded"
    scheduler_health = "running" if scheduler.is_running else "stopped"
    app_health = "healthy"

    # Determine composite system status
    if not is_connected:
        overall_status = "degraded"  # or unavailable
    elif weather_health == "degraded" or ml_health == "degraded":
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    components = {
        "application": app_health,
        "database": db_health,
        "weather": weather_health,
        "ml_model": ml_health,
        "scheduler": scheduler_health,
    }

    return HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        database=db_status,
        components=components,
        monitored_zones=telemetry["counts"]["total"],
        counts_by_risk=telemetry["counts"],
        current_precipitation_mm=telemetry["current_precipitation_mm"],
        last_weather_sync=telemetry["last_synced_at"],
    )
