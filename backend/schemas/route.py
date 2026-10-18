"""Pydantic schemas for Evacuation Routing and Path Evaluation."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class RouteRequest(BaseModel):
    """Origin coordinate payload for evacuation path calculation."""

    latitude: float = Field(..., description="Latitude coordinate between -90 and 90")
    longitude: float = Field(..., description="Longitude coordinate between -180 and 180")
    name: Optional[str] = Field(None, description="Optional place label")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude {v} out of valid range [-90.0, 90.0].")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude {v} out of valid range [-180.0, 180.0].")
        return v


class RouteGeometry(BaseModel):
    """GeoJSON LineString geometry."""

    type: str = "LineString"
    coordinates: list[list[float]]


class RouteDetails(BaseModel):
    """Calculated path performance and safety metrics."""

    distance: float
    dist_km: float
    duration: float
    duration_mins: float
    riskScore: float
    safetyScore: float
    maxRisk: str
    geometry: RouteGeometry


class RouteResponse(BaseModel):
    """Top composite safe route recommendation."""

    shelter: dict[str, Any]
    route: RouteDetails
    score: float
    reason: str


class EvacuationStartRequest(BaseModel):
    """Request payload to initiate evacuation to a designated shelter."""

    shelter_id: int = Field(..., gt=0, description="Unique shelter identifier")


class EvacuationStartResponse(BaseModel):
    """Response payload acknowledging evacuation start."""

    message: str
    shelter: dict[str, Any]
