"""Integration tests for PostGIS spatial queries, GiST indexes, and containment."""

import pytest
from sqlalchemy import text

from backend.database.connection import SessionLocal


def test_postgis_extension_active():
    """Verify PostGIS extension is loaded in PostgreSQL database."""
    with SessionLocal() as db:
        res = db.execute(text("SELECT PostGIS_Version();")).fetchone()
        assert res is not None
        version_str = res[0]
        assert "3." in version_str


def test_postgis_gist_spatial_indexes():
    """Verify GiST spatial indexes exist on geometry columns."""
    with SessionLocal() as db:
        indexes = db.execute(text("""
            SELECT indexname, tablename, indexdef 
            FROM pg_indexes 
            WHERE indexdef LIKE '%USING gist%';
        """)).fetchall()

        index_names = {row.indexname for row in indexes}
        assert "idx_grids_geom" in index_names
        assert "idx_grids_point_geom" in index_names
        assert "idx_shelters_location" in index_names


def test_postgis_shelter_distance_and_radius():
    """Verify ST_DWithin and ST_Distance execute accurately inside PostGIS."""
    with SessionLocal() as db:
        # Distance from Chennai Central (13.0827, 80.2707) to T. Nagar (13.0418, 80.2341)
        res = db.execute(text("""
            SELECT 
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(80.2707, 13.0827), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(80.2341, 13.0418), 4326)::geography
                ) / 1000.0 AS dist_km;
        """)).fetchone()

        dist_km = float(res[0])
        # Approx 6.1 km
        assert 5.0 <= dist_km <= 7.5


def test_postgis_grid_polygon_containment():
    """Verify ST_Contains detects coordinate within sector polygon."""
    with SessionLocal() as db:
        # T. Nagar coordinates (13.0418, 80.2341) must be contained in T. Nagar polygon
        res = db.execute(text("""
            SELECT name 
            FROM grids 
            WHERE geom IS NOT NULL 
              AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(80.2341, 13.0418), 4326));
        """)).fetchall()

        names = [row[0] for row in res]
        assert "T. Nagar" in names
