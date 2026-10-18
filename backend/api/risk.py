"""FastAPI router for Flood Risk evaluation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.schemas.risk import (
    MLPredictionRequest,
    MLPredictionResponse,
    RiskDetailResponse,
    RiskPointResponse,
)
from backend.services.risk_service import get_risk_service
from backend.services.shelter_service import validate_coordinates

router = APIRouter(tags=["Risk"])


@router.get("/api/risk/point", response_model=RiskPointResponse)
def get_risk_by_point(
    lat: float = Query(..., description="Latitude coordinate"),
    lng: float = Query(..., description="Longitude coordinate"),
    db: Session = Depends(get_db),
) -> RiskPointResponse:
    """Query flood hazard classification for specific coordinates using PostGIS."""
    is_valid, err = validate_coordinates(lat, lng)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err)

    risk_service = get_risk_service()
    risk_level = risk_service.query_risk_by_coordinate(db, lat, lng)

    return RiskPointResponse(
        latitude=lat,
        longitude=lng,
        risk_level=risk_level,
        probability=None,
    )


@router.get("/api/risk/{grid_id}", response_model=RiskDetailResponse)
def get_risk_by_grid_id(grid_id: int, db: Session = Depends(get_db)) -> RiskDetailResponse:
    """Retrieve stored deterministic risk indices for a specific sector ID."""
    risk_service = get_risk_service()
    grid = risk_service.get_grid_by_id(db, grid_id)
    if not grid:
        raise HTTPException(status_code=404, detail=f"Grid with ID {grid_id} not found.")

    props = grid.get("properties", {})
    return RiskDetailResponse(
        grid_id=props.get("id"),
        place_name=props.get("place_name"),
        risk_level=props.get("flood_risk"),
        risk_score=props.get("flood_risk_score"),
        probability=None,
        rainfall_mm=props.get("rainfall_mm"),
        elevation_m=props.get("elevation_m"),
        distance_to_water_m=props.get("distance_to_water"),
    )


@router.post("/api/predictions/flood", response_model=MLPredictionResponse)
def predict_flood_risk_ml(
    payload: MLPredictionRequest,
    db: Session = Depends(get_db),
) -> MLPredictionResponse:
    """Generate empirical ML flood risk forecast for specific geographical coordinates."""
    is_valid, err = validate_coordinates(payload.latitude, payload.longitude)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err)

    # Locate nearest sector via PostGIS for terrain elevation and water proximity
    from sqlalchemy import text
    from backend.models.grid import Grid
    from backend.services.ml_prediction_service import get_ml_prediction_service

    knn_query = text("""
        SELECT id, name, latitude, longitude, elevation_m, distance_to_water, rainfall_mm
        FROM grids 
        ORDER BY point_geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        LIMIT 1;
    """)

    try:
        row = db.execute(knn_query, {"lat": payload.latitude, "lng": payload.longitude}).fetchone()
    except Exception:
        row = None

    if row:
        grid_id = row.id
        place_name = row.name
        elev = float(row.elevation_m)
        water_dist = float(row.distance_to_water)
        stored_rain = float(row.rainfall_mm)
    else:
        # Defaults for Chennai city average if database has no grids
        grid_id = None
        place_name = "Chennai Urban Corridor"
        elev = 6.0
        water_dist = 1200.0
        stored_rain = 0.0

    current_rain = float(payload.rainfall_mm) if payload.rainfall_mm is not None else stored_rain

    ml_service = get_ml_prediction_service()
    pred_res = ml_service.predict_sector_risk(
        rainfall_current_mm=current_rain,
        rainfall_3d_accum_mm=current_rain * 1.5,
        rainfall_7d_accum_mm=current_rain * 2.2,
        elevation_m=elev,
        distance_to_water_m=water_dist,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )

    return MLPredictionResponse(
        grid_id=grid_id,
        place_name=place_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        prediction=pred_res["prediction"],
        probability=pred_res["probability"],
        model_version=pred_res["model_version"],
        algorithm=pred_res["algorithm"],
        prediction_horizon=pred_res["prediction_horizon"],
        is_fallback=pred_res["is_fallback"],
        contributing_features=pred_res["contributing_features"],
    )
