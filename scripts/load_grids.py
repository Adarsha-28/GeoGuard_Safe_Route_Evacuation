#!/usr/bin/env python3
"""Idempotent data loader for Chennai risk grid places into PostGIS with spatial polygons."""

from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path
from shapely.geometry import Point, mapping
from shapely import wkt

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_GeomFromText, ST_MakePoint, ST_SetSRID
from sqlalchemy.orm import Session

from backend.config import PLACES_CSV_PATH
from backend.database.connection import SessionLocal
from backend.models.grid import Grid
from backend.services.risk_service import get_risk_service


def create_sector_polygon_wkt(lat: float, lng: float, radius_km: float = 1.2, num_points: int = 24) -> str:
    """Generate a polygon WKT representing the spatial boundary of a monitored sector."""
    # 1 deg latitude ~ 111 km, 1 deg longitude ~ 111 * cos(lat) km
    lat_deg = radius_km / 111.0
    lng_deg = radius_km / (111.0 * math.cos(math.radians(lat)))

    coords = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        pt_lat = lat + (lat_deg * math.sin(angle))
        pt_lng = lng + (lng_deg * math.cos(angle))
        coords.append(f"{pt_lng:.6f} {pt_lat:.6f}")
    # Close polygon
    coords.append(coords[0])
    return f"POLYGON(({', '.join(coords)}))"


def load_grids(db: Session, csv_path: Path | None = None) -> int:
    """Load places CSV and populate grids table with Point and Polygon PostGIS geometries."""
    path = csv_path or PLACES_CSV_PATH
    if not path.exists():
        raise FileNotFoundError(f"Places CSV not found at {path}")

    inserted = 0
    updated = 0

    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            place_name = row["place"].strip()
            lat = float(str(row["latitude"]).strip())
            lng = float(str(row["longitude"]).strip())
            elev = float(str(row["elevation_m"]).strip())
            raw_dist = str(row["distance_to_water"]).strip()
            import re
            cleaned_dist = re.sub(r"[^\d.]", "", raw_dist) or "0.0"
            water_dist = float(cleaned_dist)

            poly_wkt = create_sector_polygon_wkt(lat, lng, radius_km=1.2)
            poly_geom = WKTElement(poly_wkt, srid=4326)
            pt_geom = ST_SetSRID(ST_MakePoint(lng, lat), 4326)

            existing = db.query(Grid).filter(Grid.name == place_name).first()

            if not existing:
                grid = Grid(
                    name=place_name,
                    latitude=lat,
                    longitude=lng,
                    elevation_m=elev,
                    distance_to_water=water_dist,
                    rainfall_mm=0.0,
                    flood_risk_score=0.0,
                    flood_risk="Low",
                    geom=poly_geom,
                    point_geom=pt_geom,
                )
                db.add(grid)
                inserted += 1
            else:
                existing.latitude = lat
                existing.longitude = lng
                existing.elevation_m = elev
                existing.distance_to_water = water_dist
                existing.geom = poly_geom
                existing.point_geom = pt_geom
                updated += 1

    db.commit()
    print(f"[OK] Grid sectors loaded: {inserted} inserted, {updated} updated.")

    # Initialize deterministic flood risk calculation
    risk_service = get_risk_service()
    risk_service.recalculate_all_risks(db, measured_rainfall_mm=0.0)
    print("[OK] Baseline deterministic flood risk scores computed and stored.")

    total = db.query(Grid).count()
    return total


def main() -> int:
    print("=" * 60)
    print("   GeoGuard V2 — Loading Geospatial Grids into PostGIS")
    print("=" * 60)
    with SessionLocal() as db:
        total = load_grids(db)
        print(f"[SUCCESS] Total monitored sectors in PostGIS: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
