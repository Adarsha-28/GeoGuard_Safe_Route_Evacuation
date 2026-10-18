"""Deterministic flood risk calculation and PostGIS geospatial grid service.

V1 -> V2 Risk Scoring Preservation:
  GeoGuard V2 strictly preserves the deterministic multi-criteria engineering model:
  1. Rainfall (50% weight): Live or stored precipitation normalized against 150mm threshold.
  2. Elevation (25% weight): Inverted digital elevation model (lower elevation = higher hazard).
  3. Water Proximity (25% weight): Inverted distance to water body (closer = higher hazard).

  Formula:
    rainfall_score = min(1.0, rainfall_mm / 150.0)
    elevation_score = (max_elevation - elevation_m) / (max_elevation - min_elevation)
    water_proximity_score = (max_water_dist - distance_to_water_m) / (max_water_dist - min_water_dist)
    risk_score = (0.50 * rainfall_score) + (0.25 * elevation_score) + (0.25 * water_proximity_score)

  Engineering Thresholds:
    - LOW:      0.00 <= score < 0.30
    - MODERATE: 0.30 <= score < 0.60
    - HIGH:     0.60 <= score < 0.85
    - SEVERE:   0.85 <= score <= 1.00
"""

from __future__ import annotations

import csv
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from backend.config import (
    CHENNAI_CENTER_LAT,
    CHENNAI_CENTER_LNG,
    GEOJSON_PATH,
    PLACES_CSV_PATH,
    logger,
)
from backend.models.grid import Grid
from backend.models.risk import RiskPrediction


def calculate_flood_risk_score(
    rainfall_score: float,
    elevation_score: float,
    water_proximity_score: float,
    rain_weight: float = 0.50,
    elev_weight: float = 0.25,
    water_weight: float = 0.25,
) -> float:
    """Calculate deterministic flood risk score strictly bounded in [0.0, 1.0]."""
    total_w = rain_weight + elev_weight + water_weight
    if total_w <= 0:
        total_w = 1.0
    w_r = rain_weight / total_w
    w_e = elev_weight / total_w
    w_w = water_weight / total_w

    r_clamped = max(0.0, min(1.0, float(rainfall_score)))
    e_clamped = max(0.0, min(1.0, float(elevation_score)))
    w_clamped = max(0.0, min(1.0, float(water_proximity_score)))

    score = (w_r * r_clamped) + (w_e * e_clamped) + (w_w * w_clamped)
    return round(float(max(0.0, min(1.0, score))), 4)


def classify_risk_level(score: float) -> str:
    """Map deterministic score to standard categorical risk level."""
    if score < 0.30:
        return "Low"
    if score < 0.60:
        return "Moderate"
    if score < 0.85:
        return "High"
    return "Severe"


class RiskService:
    """Service managing flood risk calculations, PostGIS grid indexing, and telemetry."""

    def __init__(self, places_csv_path: Path | str | None = None) -> None:
        self.places_csv = Path(places_csv_path or PLACES_CSV_PATH)
        self._lock = threading.Lock()
        self._current_precipitation_mm: float = 0.0
        self._last_sync_timestamp: str | None = None
        self._weather_sync_status: str = "initialized"
        self._cached_geojson: dict[str, Any] | None = None

    def query_risk_by_coordinate(self, db: Session, lat: float, lng: float) -> str:
        """Query flood risk level using PostGIS spatial queries.
        
        Algorithm:
        1. Query polygon sector containment using ST_Contains(geom, ST_SetSRID(ST_MakePoint(lng, lat), 4326)).
        2. If outside exact sector polygons, use PostGIS GiST index KNN operator (<->)
           to locate the nearest sector in O(log N) time.
        No full table scanning in Python.
        """
        # 1. Check polygon containment
        containment_query = text("""
            SELECT flood_risk 
            FROM grids 
            WHERE geom IS NOT NULL 
              AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
            LIMIT 1;
        """)
        try:
            row = db.execute(containment_query, {"lat": lat, "lng": lng}).fetchone()
            if row:
                return str(row[0])

            # 2. KNN nearest point fallback
            knn_query = text("""
                SELECT flood_risk 
                FROM grids 
                ORDER BY point_geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
                LIMIT 1;
            """)
            knn_row = db.execute(knn_query, {"lat": lat, "lng": lng}).fetchone()
            if knn_row:
                return str(knn_row[0])
        except Exception as e:
            logger.warning(f"PostGIS risk query error, using database fallback: {e}")
            grid = db.query(Grid).first()
            if grid:
                return grid.flood_risk

        return "Low"

    def recalculate_all_risks(self, db: Session, measured_rainfall_mm: float = 0.0) -> dict[str, Any]:
        """Deterministically calculate risk scores for all grid sectors in PostgreSQL."""
        with self._lock:
            self._current_precipitation_mm = max(0.0, float(measured_rainfall_mm))

            grids = db.query(Grid).all()
            if not grids:
                logger.warning("No grids found in database to recalculate.")
                return {"type": "FeatureCollection", "name": "chennai_places_risk", "features": []}

            elevations = [g.elevation_m for g in grids]
            water_distances = [g.distance_to_water for g in grids]

            min_elev, max_elev = min(elevations), max(elevations)
            min_water, max_water = min(water_distances), max(water_distances)

            elev_range = max_elev - min_elev if (max_elev - min_elev) > 0 else 1.0
            water_range = max_water - min_water if (max_water - min_water) > 0 else 1.0
            rain_reference_max = 150.0

            features = []
            now_dt = datetime.utcnow()

            for g in grids:
                g.rainfall_mm = self._current_precipitation_mm

                r_score = min(1.0, g.rainfall_mm / rain_reference_max)
                e_score = (max_elev - g.elevation_m) / elev_range
                w_score = (max_water - g.distance_to_water) / water_range

                score = calculate_flood_risk_score(
                    rainfall_score=r_score,
                    elevation_score=e_score,
                    water_proximity_score=w_score,
                )
                level = classify_risk_level(score)

                g.flood_risk_score = score
                g.flood_risk = level

                # Query ML forecast if available
                from backend.services.ml_prediction_service import get_ml_prediction_service
                ml_service = get_ml_prediction_service()
                ml_pred = ml_service.predict_sector_risk(
                    rainfall_current_mm=g.rainfall_mm,
                    rainfall_3d_accum_mm=g.rainfall_mm * 1.5,
                    rainfall_7d_accum_mm=g.rainfall_mm * 2.2,
                    elevation_m=g.elevation_m,
                    distance_to_water_m=g.distance_to_water,
                    latitude=g.latitude,
                    longitude=g.longitude,
                )

                # Record historical snapshot
                prediction = RiskPrediction(
                    grid_id=g.id,
                    risk_score=score,
                    risk_level=level,
                    rainfall_score=round(r_score, 4),
                    elevation_score=round(e_score, 4),
                    water_proximity_score=round(w_score, 4),
                    model_version=ml_pred["model_version"],
                    probability=ml_pred["probability"],
                    prediction_horizon=ml_pred["prediction_horizon"],
                    is_fallback=ml_pred["is_fallback"],
                    calculated_at=now_dt,
                )
                db.add(prediction)

                feat = g.to_geojson_feature()
                feat["properties"]["ml_risk"] = ml_pred["prediction"]
                feat["properties"]["ml_probability"] = ml_pred["probability"]
                feat["properties"]["model_version"] = ml_pred["model_version"]
                features.append(feat)

            db.commit()

            self._cached_geojson = {
                "type": "FeatureCollection",
                "name": "chennai_places_risk",
                "features": features,
            }
            return self._cached_geojson

    def get_all_grids(self, db: Session, model: str = "ml") -> dict[str, Any]:
        """Return GeoJSON FeatureCollection with either V3 ML forecast or V2 deterministic scoring."""
        grids = db.query(Grid).order_by(Grid.id.asc()).all()
        features = []

        from backend.services.ml_prediction_service import get_ml_prediction_service
        ml_service = get_ml_prediction_service()

        for g in grids:
            feat = g.to_geojson_feature()
            ml_pred = ml_service.predict_sector_risk(
                rainfall_current_mm=g.rainfall_mm,
                rainfall_3d_accum_mm=g.rainfall_mm * 1.5,
                rainfall_7d_accum_mm=g.rainfall_mm * 2.2,
                elevation_m=g.elevation_m,
                distance_to_water_m=g.distance_to_water,
                latitude=g.latitude,
                longitude=g.longitude,
            )

            feat["properties"]["ml_risk"] = ml_pred["prediction"]
            feat["properties"]["ml_probability"] = ml_pred["probability"]
            feat["properties"]["model_version"] = ml_pred["model_version"]
            feat["properties"]["algorithm"] = ml_pred["algorithm"]
            feat["properties"]["is_fallback"] = ml_pred["is_fallback"]
            feat["properties"]["contributing_features"] = ml_pred["contributing_features"]

            # If user requests ML model, map primary flood_risk to ML forecast
            if model.lower() == "ml" and not ml_pred["is_fallback"]:
                feat["properties"]["flood_risk"] = ml_pred["prediction"]
                feat["properties"]["flood_risk_score"] = ml_pred["probability"]

            features.append(feat)

        return {
            "type": "FeatureCollection",
            "name": "chennai_places_risk",
            "model": model.lower(),
            "features": features,
        }

    def get_grid_by_id(self, db: Session, grid_id: int) -> dict[str, Any] | None:
        """Find a single grid sector feature by ID."""
        grid = db.query(Grid).filter(Grid.id == grid_id).first()
        return grid.to_geojson_feature() if grid else None

    def get_telemetry_summary(self, db: Session) -> dict[str, Any]:
        """Return risk counts and telemetry metadata."""
        grids = db.query(Grid).all()
        counts = {"safe": 0, "moderate": 0, "high": 0, "severe": 0, "total": len(grids)}

        for g in grids:
            if g.flood_risk == "Low":
                counts["safe"] += 1
            elif g.flood_risk == "Moderate":
                counts["moderate"] += 1
            elif g.flood_risk == "High":
                counts["high"] += 1
            elif g.flood_risk == "Severe":
                counts["severe"] += 1

        with self._lock:
            return {
                "counts": counts,
                "current_precipitation_mm": self._current_precipitation_mm,
                "last_synced_at": self._last_sync_timestamp,
                "weather_sync_status": self._weather_sync_status,
            }

    def update_weather_status(self, current_rain: float, timestamp_iso: str, status: str) -> None:
        """Update in-memory telemetry cache from weather synchronization."""
        with self._lock:
            self._current_precipitation_mm = current_rain
            self._last_sync_timestamp = timestamp_iso
            self._weather_sync_status = status


_singleton_risk_service: RiskService | None = None


def get_risk_service() -> RiskService:
    """Retrieve singleton instance of RiskService."""
    global _singleton_risk_service
    if _singleton_risk_service is None:
        _singleton_risk_service = RiskService()
    return _singleton_risk_service
