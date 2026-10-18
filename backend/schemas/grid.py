"""Pydantic schemas for Geospatial Grid responses."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class GridProperties(BaseModel):
    """Properties for monitored Chennai grid sector."""

    id: int
    place_name: str
    latitude: float
    longitude: float
    elevation_m: float
    distance_to_water: float
    rainfall_mm: float
    flood_risk_score: float
    flood_risk: str


class PointGeometry(BaseModel):
    """GeoJSON Point geometry."""

    type: Literal["Point"] = "Point"
    coordinates: list[float]  # [longitude, latitude]


class GridFeature(BaseModel):
    """GeoJSON Feature for a grid sector."""

    type: Literal["Feature"] = "Feature"
    id: int
    properties: GridProperties
    geometry: PointGeometry


class GridCollectionResponse(BaseModel):
    """GeoJSON FeatureCollection response containing all monitored grid cells."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    name: str = "chennai_places_risk"
    features: list[dict[str, Any]]
