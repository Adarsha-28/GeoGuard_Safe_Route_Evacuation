"""Pydantic schemas for Emergency Alerts."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.models.alert import VALID_SEVERITIES


class AlertCreate(BaseModel):
    """Payload to create and broadcast an administrative emergency alert."""

    title: str = Field(..., min_length=1, max_length=200)
    severity: str = Field(..., description="Alert severity level")
    zone: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1)

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        v_stripped = v.strip()
        if v_stripped not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{v}'. Must be one of {sorted(VALID_SEVERITIES)}."
            )
        return v_stripped

    @field_validator("title", "zone", "message")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Field cannot be empty or whitespace only.")
        return v_stripped


class AlertResponse(BaseModel):
    """Emergency alert bulletin representation."""

    id: int
    grid_id: int | None = None
    title: str
    severity: str
    zone: str
    message: str
    previous_risk: str | None = None
    current_risk: str | None = None
    probability: float | None = None
    model_version: str | None = None
    is_active: bool = True
    isActive: int = 1
    timestamp: str
    created_at: str | None = None


class AlertCreateResponse(BaseModel):
    """Response returned upon successfully creating an alert."""

    message: str = "Alert published successfully."
    alert: AlertResponse


class AlertAcknowledgeResponse(BaseModel):
    """Response returned upon acknowledging an alert."""

    message: str = "Alert acknowledged and deactivated."
    alert: AlertResponse
