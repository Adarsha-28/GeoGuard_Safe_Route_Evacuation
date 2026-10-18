#!/usr/bin/env python3
"""Empirical performance benchmark: Python Haversine (V1) vs PostGIS Spatial Queries (V2)."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from backend.database.connection import SessionLocal
from backend.models.shelter import Shelter
from backend.services.shelter_service import haversine_distance


def benchmark_v1_python_haversine(db, test_lat: float, test_lng: float, radius_km: float, iterations: int = 100):
    """V1 Approach: Load all shelters into Python memory and compute Haversine distances in a loop."""
    shelters = db.query(Shelter).all()
    records = [
        {"id": s.id, "lat": s.latitude, "lng": s.longitude, "cap": s.available_capacity}
        for s in shelters
    ]

    t0 = time.perf_counter()
    for _ in range(iterations):
        nearby = []
        for s in records:
            if s["cap"] <= 0:
                continue
            d = haversine_distance(test_lat, test_lng, s["lat"], s["lng"])
            if d <= radius_km:
                s_copy = dict(s)
                s_copy["distance"] = d
                nearby.append(s_copy)
        nearby.sort(key=lambda x: x["distance"])
        top_results = nearby[:5]
    t1 = time.perf_counter()

    avg_ms = ((t1 - t0) / iterations) * 1000.0
    return avg_ms, len(top_results)


def benchmark_v2_postgis_spatial(db, test_lat: float, test_lng: float, radius_km: float, iterations: int = 100):
    """V2 Approach: Execute PostGIS database-side ST_DWithin and ST_Distance query with GiST index."""
    query = text("""
        SELECT id, name, latitude, longitude,
               ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) / 1000.0 AS dist_km
        FROM shelters
        WHERE is_active = true
          AND available_capacity > 0
          AND ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_m)
        ORDER BY dist_km ASC
        LIMIT 5;
    """)

    params = {
        "lat": test_lat,
        "lng": test_lng,
        "radius_m": radius_km * 1000.0,
    }

    t0 = time.perf_counter()
    for _ in range(iterations):
        res = db.execute(query, params).fetchall()
    t1 = time.perf_counter()

    avg_ms = ((t1 - t0) / iterations) * 1000.0
    return avg_ms, len(res)


def inspect_postgis_query_plan(db, test_lat: float, test_lng: float, radius_km: float) -> str:
    """Run EXPLAIN ANALYZE on the spatial shelter search to verify GiST index usage."""
    query = text("""
        EXPLAIN ANALYZE
        SELECT id, name,
               ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) / 1000.0 AS dist_km
        FROM shelters
        WHERE is_active = true
          AND available_capacity > 0
          AND ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_m)
        ORDER BY dist_km ASC
        LIMIT 5;
    """)
    res = db.execute(query, {"lat": test_lat, "lng": test_lng, "radius_m": radius_km * 1000.0}).fetchall()
    return "\n".join(row[0] for row in res)


def main() -> int:
    print("=" * 65)
    print("   GeoGuard V2 — Spatial Performance Benchmark")
    print("=" * 65)

    test_lat = 13.0418  # T. Nagar
    test_lng = 80.2341
    radius_km = 20.0
    iterations = 200

    print(f"Test Coordinates: ({test_lat}, {test_lng}) | Radius: {radius_km} km | Iterations: {iterations}\n")

    with SessionLocal() as db:
        print("[..] Benchmarking V1 Python Haversine Loop (In-Memory)...")
        v1_avg_ms, v1_count = benchmark_v1_python_haversine(db, test_lat, test_lng, radius_km, iterations)
        print(f"[OK] V1 Average Time: {v1_avg_ms:.4f} ms (Retrieved {v1_count} results)")

        print("\n[..] Benchmarking V2 PostGIS Database Spatial Query (ST_DWithin)...")
        v2_avg_ms, v2_count = benchmark_v2_postgis_spatial(db, test_lat, test_lng, radius_km, iterations)
        print(f"[OK] V2 Average Time: {v2_avg_ms:.4f} ms (Retrieved {v2_count} results)")

        print("\n[..] PostGIS Query Execution Plan (EXPLAIN ANALYZE):")
        print("-" * 65)
        try:
            plan = inspect_postgis_query_plan(db, test_lat, test_lng, radius_km)
            print(plan)
        except Exception as e:
            print(f"Query plan inspection notice: {e}")
        print("-" * 65)

        print("\n" + "=" * 65)
        print("   Architectural Analysis:")
        print("   - For small local datasets (25 shelters), Python in-memory math is fast")
        print("     due to no database network round-trip overhead.")
        print("   - However, PostGIS scales to 10,000+ points using GiST spatial R-tree")
        print("     indexing, bounding-box pre-filtering, and concurrent multi-user execution,")
        print("     completely offloading distance math and filtering from application workers.")
        print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
