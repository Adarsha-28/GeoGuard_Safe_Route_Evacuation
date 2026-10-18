#!/usr/bin/env python3
"""GeoGuard V4 — Automated Prediction Pipeline Latency Benchmark.

Empirically benchmarks the four primary operational stages:
1. Feature Generation Latency
2. ML Model Inference Latency
3. Database Audit Persistence Latency
4. Complete Operational Cycle Latency

Calculates exact empirical Average, Median (p50), and 95th Percentile (p95)
latency distributions over configurable benchmark iterations.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from statistics import mean, median

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
from sqlalchemy.orm import Session

from backend.database.connection import SessionLocal
from backend.models.grid import Grid
from backend.models.risk import RiskPrediction
from backend.services.feature_service import get_feature_service
from backend.services.ml_prediction_service import get_ml_prediction_service
from backend.services.prediction_pipeline_service import get_prediction_pipeline_service
from backend.services.risk_state_service import get_risk_state_service
from backend.services.weather_ingestion_service import WeatherIngestionResult, get_weather_ingestion_service


def calculate_percentile(data: list[float], percentile: float) -> float:
    """Compute empirical percentile value."""
    if not data:
        return 0.0
    arr = sorted(data)
    k = (len(arr) - 1) * (percentile / 100.0)
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    d = k - f
    return arr[f] + d * (arr[c] - arr[f])


def run_benchmarks(iterations: int = 20) -> dict[str, dict[str, float]]:
    """Execute latency benchmark across iterations."""
    print("=" * 70)
    print(f"   GeoGuard V4 — Operational Pipeline Latency Benchmark")
    print(f"   Sample Size: {iterations} iterations across all 34 monitored sectors")
    print("=" * 70)

    feature_service = get_feature_service()
    ml_service = get_ml_prediction_service()
    pipeline_service = get_prediction_pipeline_service()
    weather_service = get_weather_ingestion_service()
    risk_state_service = get_risk_state_service()

    with SessionLocal() as db:
        grids = db.query(Grid).order_by(Grid.id.asc()).all()
        if not grids:
            print("[ERROR] No grids found in database to benchmark.")
            return {}

        total_grids = len(grids)
        print(f"[INFO] Monitored grids: {total_grids} sectors loaded from PostGIS.")
        print(f"[INFO] ML Model Active: {ml_service.model_version} ({ml_service.is_available})")

        # Create realistic mock weather observation result to benchmark pipeline deterministically
        mock_weather = WeatherIngestionResult(
            success=True,
            rainfall_current_mm=38.5,
            wind_speed_kmh=18.2,
            daily_rainfall_history=[12.0, 5.0, 22.0, 0.0, 15.0, 30.0, 38.5],
            is_duplicate=False,
        )

        feat_latencies: list[float] = []
        ml_latencies: list[float] = []
        db_latencies: list[float] = []
        full_cycle_latencies: list[float] = []

        print("\n[..] Running benchmark iterations...")

        for it in range(iterations):
            # 1. Feature Generation Benchmark (for all 34 grids)
            t0 = time.perf_counter()
            feature_results = []
            for g in grids:
                fr = feature_service.generate_sector_features(
                    grid=g,
                    rainfall_current_mm=38.5,
                    rainfall_3d_accum_mm=83.5,
                    rainfall_7d_accum_mm=122.5,
                )
                feature_results.append(fr)
            t_feat = (time.perf_counter() - t0) * 1000.0
            feat_latencies.append(t_feat)

            # 2. ML Inference Benchmark (for all 34 grids)
            t1 = time.perf_counter()
            predictions = []
            for g, fr in zip(grids, feature_results):
                pred = ml_service.predict_sector_risk(
                    rainfall_current_mm=fr.features["rainfall_current_mm"],
                    rainfall_3d_accum_mm=fr.features["rainfall_3d_accum_mm"],
                    rainfall_7d_accum_mm=fr.features["rainfall_7d_accum_mm"],
                    elevation_m=fr.features["elevation_m"],
                    distance_to_water_m=fr.features["distance_to_water_m"],
                    latitude=fr.features["latitude"],
                    longitude=fr.features["longitude"],
                    month=fr.features["month"],
                )
                predictions.append(pred)
            t_ml = (time.perf_counter() - t1) * 1000.0
            ml_latencies.append(t_ml)

            # 3. Database Persistence Benchmark (insert 34 audit records and rollback)
            t2 = time.perf_counter()
            for g, pred in zip(grids, predictions):
                rec = RiskPrediction(
                    grid_id=g.id,
                    risk_score=float(pred["probability"]),
                    risk_level=str(pred["prediction"]),
                    rainfall_score=0.25,
                    elevation_score=0.35,
                    water_proximity_score=0.45,
                    model_version=pred["model_version"],
                    probability=pred["probability"],
                    prediction_horizon=pred["prediction_horizon"],
                    is_fallback=pred["is_fallback"],
                    trigger_type="benchmark",
                )
                db.add(rec)
            db.flush()
            t_db = (time.perf_counter() - t2) * 1000.0
            db.rollback()  # Do not pollute database with benchmark records
            db_latencies.append(t_db)

            # 4. Full Operational Cycle (End-to-End Pipeline)
            t3 = time.perf_counter()
            res = pipeline_service.run_prediction_pipeline(
                db=db,
                weather_result=mock_weather,
                trigger_type="benchmark",
            )
            transitions = risk_state_service.update_grid_risk_states(db, res.predictions)
            t_full = (time.perf_counter() - t3) * 1000.0
            full_cycle_latencies.append(t_full)

            if (it + 1) % 5 == 0:
                print(f"     Completed {it + 1}/{iterations} iterations...")

    # Compile Statistics
    metrics = {
        "Feature Generation (34 sectors)": feat_latencies,
        "ML Inference (34 sectors)": ml_latencies,
        "DB Persistence (34 audit records)": db_latencies,
        "Complete Pipeline Cycle": full_cycle_latencies,
    }

    results = {}
    print("\n" + "=" * 70)
    print(f"{'Operational Component':<36} | {'Avg (ms)':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10}")
    print("-" * 70)

    for name, lat_list in metrics.items():
        avg_v = mean(lat_list)
        p50_v = median(lat_list)
        p95_v = calculate_percentile(lat_list, 95)
        results[name] = {
            "average_ms": round(avg_v, 2),
            "p50_ms": round(p50_v, 2),
            "p95_ms": round(p95_v, 2),
        }
        print(f"{name:<36} | {avg_v:8.2f} ms | {p50_v:8.2f} ms | {p95_v:8.2f} ms")

    print("=" * 70)
    return results


if __name__ == "__main__":
    run_benchmarks(iterations=20)
