"""FastAPI router for Open-Meteo Weather Synchronization."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.risk import WeatherSyncResponse
from backend.services.weather_service import get_weather_service

router = APIRouter(tags=["Weather"])


@router.post("/api/weather/sync", response_model=WeatherSyncResponse)
@router.post("/api/weather/update", response_model=WeatherSyncResponse, include_in_schema=False)
def sync_weather(db: Session = Depends(get_db)) -> WeatherSyncResponse:
    """Trigger live weather synchronization from Open-Meteo and update risk scores."""
    weather_service = get_weather_service()
    success, current_rain, timestamp = weather_service.sync_live_weather(db)

    if success:
        return WeatherSyncResponse(
            message="Weather and flood risk indices synchronized successfully.",
            measured_rainfall_mm=current_rain,
            synced_at=timestamp,
        )
    else:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch live weather from external service. Using existing stored risk values.",
        )
