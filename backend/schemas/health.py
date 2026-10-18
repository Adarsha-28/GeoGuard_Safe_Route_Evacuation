"""Pydantic schemas for System Health and Telemetry Status."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """System health status and telemetry overview."""

    status: str = Field(..., description="'healthy', 'degraded', or 'unavailable'")
    version: str = "2.0.0"
    database: str = Field(..., description="PostgreSQL connection state")
    components: dict[str, str] = Field(
        default_factory=lambda: {
            "application": "healthy",
            "database": "healthy",
            "weather": "healthy",
            "ml_model": "healthy",
            "scheduler": "running",
        },
        description="Component-level health statuses",
    )
    monitored_zones: int = 0
    counts_by_risk: dict[str, int] = Field(default_factory=dict)
    current_precipitation_mm: float = 0.0
    last_weather_sync: Optional[str] = None
