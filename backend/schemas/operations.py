"""Pydantic schemas for Operational Intelligence Telemetry and Control."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class OperationsStatusResponse(BaseModel):
    """Real-time operational status of GeoGuard intelligence services."""

    weather_status: str = Field(..., description="'healthy', 'degraded', or 'unavailable'")
    last_weather_sync: str | None = Field(None, description="ISO timestamp of last successful weather fetch")
    last_prediction_run: str | None = Field(None, description="ISO timestamp of last prediction cycle")
    next_prediction_run: str | None = Field(None, description="ISO timestamp of next scheduled prediction cycle")
    model_version: str = Field(..., description="Active flood model version string")
    active_model: str = Field(..., description="Algorithm name currently handling inference")
    fallback_active: bool = Field(..., description="True if deterministic fallback is handling inference")
    active_alerts: int = Field(..., description="Count of currently active emergency alerts")
    high_risk_grids: int = Field(..., description="Count of monitored sectors in High or Severe risk")
    prediction_latency_ms: float = Field(0.0, description="Execution latency of the last prediction cycle")
    scheduler_status: str = Field("running", description="'running' or 'stopped'")
    cycles_completed: int = 0
    cycles_skipped: int = 0
    cycles_failed: int = 0


class OperationalCycleTriggerResponse(BaseModel):
    """Response returned when triggering an operational prediction cycle on demand."""

    status: str
    trigger_type: str = "manual"
    latency_ms: float = 0.0
    total_grids: int = 0
    transitions_detected: int = 0
    new_alerts_issued: int = 0
    fallback_active: bool = False
    model_version: str = ""
    active_model: str = ""
    completed_at: str | None = None
    reason: str | None = None
    error: str | None = None
