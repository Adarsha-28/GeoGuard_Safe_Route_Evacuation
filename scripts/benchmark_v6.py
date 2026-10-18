"""GeoGuard V6 Performance Benchmarking Suite.

Measures latency profiles for:
1. Single-sector simulation inference
2. 34-sector batch scenario simulation
3. Shelter capacity stress test evaluation
4. Multi-path route resilience evaluation
5. Full scenario simulation pipeline (End-to-End)

Computes Mean, Min, Max, and P95 latency across iterations.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import time
import numpy as np

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session
from backend.database.connection import SessionLocal
from backend.services.adaptive_evacuation_service import get_adaptive_evacuation_service
from backend.services.resilience_scoring_service import get_resilience_scoring_service
from backend.services.route_resilience_service import get_route_resilience_service
from backend.services.scenario_simulation_service import get_scenario_simulation_service
from backend.services.spatial_propagation_service import get_spatial_propagation_service


def run_benchmarks(iterations: int = 5) -> dict[str, dict[str, float]]:
    print(f"==================================================")
    print(f" GeoGuard V6 Performance Benchmarking ({iterations} iterations)")
    print(f"==================================================")

    scenario_svc = get_scenario_simulation_service()
    evac_svc = get_adaptive_evacuation_service()
    route_svc = get_route_resilience_service()
    resilience_svc = get_resilience_scoring_service()
    spatial_svc = get_spatial_propagation_service()

    metrics: dict[str, list[float]] = {
        "shelter_stress_test": [],
        "route_resilience_evaluation": [],
        "resilience_score_computation": [],
        "spatial_risk_propagation": [],
        "full_scenario_simulation_pipeline": [],
    }

    with SessionLocal() as db:
        # Pre-seed simulated sector risks
        sim_risks = {i: "High" if i % 4 == 0 else "Moderate" if i % 2 == 0 else "Low" for i in range(1, 35)}
        dummy_sector_results = [
            {
                "grid_id": i,
                "baseline_risk": "Low",
                "simulated_risk": sim_risks[i],
                "probability_delta": 0.35 if sim_risks[i] != "Low" else 0.05,
                "is_transitioned": sim_risks[i] != "Low",
            }
            for i in range(1, 35)
        ]

        # 1. Benchmark Shelter Stress Test
        print("\n[1/5] Benchmarking Shelter Capacity Stress Testing...")
        for _ in range(iterations):
            t0 = time.perf_counter()
            evac_svc.evaluate_shelter_stress(db, sim_risks, simulation_demand_factor=1.5)
            metrics["shelter_stress_test"].append((time.perf_counter() - t0) * 1000.0)

        # 2. Benchmark Route Resilience Evaluation (origin grid 1 to shelter 1)
        print("[2/5] Benchmarking Route Resilience Multi-Path Evaluation...")
        for _ in range(iterations):
            t0 = time.perf_counter()
            route_svc.evaluate_route_alternatives(db, origin_grid_id=1, primary_shelter_id=1, backup_shelter_id=2, simulated_sector_risks=sim_risks)
            metrics["route_resilience_evaluation"].append((time.perf_counter() - t0) * 1000.0)

        # 3. Benchmark Spatial Risk Propagation
        print("[3/5] Benchmarking Spatial Risk Propagation...")
        for _ in range(iterations):
            t0 = time.perf_counter()
            spatial_svc.analyze_propagation(db, dummy_sector_results)
            metrics["spatial_risk_propagation"].append((time.perf_counter() - t0) * 1000.0)

        # 4. Benchmark Resilience Scoring Computation
        print("[4/5] Benchmarking 5-Factor Resilience Scoring Computation...")
        for _ in range(iterations):
            t0 = time.perf_counter()
            resilience_svc.compute_resilience(db)
            metrics["resilience_score_computation"].append((time.perf_counter() - t0) * 1000.0)

        # 5. Benchmark Full Scenario Simulation Pipeline (End-to-End)
        print("[5/5] Benchmarking Full Scenario Simulation Pipeline (End-to-End)...")
        for i in range(iterations):
            t0 = time.perf_counter()
            scenario_svc.simulate(
                db=db,
                name=f"Benchmark Run #{i+1}",
                rainfall_multiplier=1.50,
                horizon="6h",
                simulation_demand_factor=1.25,
                description="Benchmark timing evaluation",
                operator="Benchmark Harness",
            )
            metrics["full_scenario_simulation_pipeline"].append((time.perf_counter() - t0) * 1000.0)

    # Calculate summaries
    results: dict[str, dict[str, float]] = {}
    print("\n" + "=" * 68)
    print(f"{'Operation':<36} | {'Mean (ms)':<9} | {'Min (ms)':<8} | {'P95 (ms)':<8}")
    print("-" * 68)
    for name, latencies in metrics.items():
        arr = np.array(latencies)
        mean_v = float(np.mean(arr))
        min_v = float(np.min(arr))
        max_v = float(np.max(arr))
        p95_v = float(np.percentile(arr, 95))
        results[name] = {
            "mean_ms": round(mean_v, 2),
            "min_ms": round(min_v, 2),
            "max_ms": round(max_v, 2),
            "p95_ms": round(p95_v, 2),
        }
        print(f"{name:<36} | {mean_v:<9.2f} | {min_v:<8.2f} | {p95_v:<8.2f}")
    print("=" * 68)
    return results


if __name__ == "__main__":
    run_benchmarks(iterations=3)
