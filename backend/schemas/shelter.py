"""Pydantic schemas for Relief Shelters."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ShelterResponse(BaseModel):
    """Shelter details matching V1 frontend contract with camelCase naming."""

    id: int
    name: str
    latitude: float
    longitude: float
    address: str
    capacity: int
    availableCapacity: int = Field(..., alias="availableCapacity")
    riskLevel: str = Field(..., alias="riskLevel")
    isActive: int = Field(1, alias="isActive")
    facilities: str
    contact: str
    distance: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True)


class EvacuationStartRequest(BaseModel):
    """Request payload to initiate evacuation to a designated shelter."""

    shelter_id: int = Field(..., gt=0, description="Unique shelter identifier")


class EvacuationStartResponse(BaseModel):
    """Response payload acknowledging evacuation start."""

    message: str
    shelter: ShelterResponse
