"""Scenario Simulation Master Service for GeoGuard V6.

Orchestrates multi-horizon flood scenario stress simulations:
- Feature 1: Modifies rainfall vectors by multiplier without model retraining.
- Feature 2: PostGIS spatial risk propagation & adjacency clustering.
- Feature 3: Adaptive evacuation planner & priority ranking.
- Feature 4: Shelter capacity stress testing (1.0x, 1.25x, 1.5x, 2.0x).
- Feature 5: Multi-path route resilience (Primary, Alt 1, Alt 2).
- Feature 6: 5-factor mathematical resilience scoring.
- Feature 10: Full operational decision audit logging.
- Strictly adheres to disclaimer: 'SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA'.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.scenario import (
    DecisionAuditLog,
    ResilienceAssessment,
    Scenario,
    ScenarioRouteResult,
    ScenarioSectorResult,
    ScenarioShelterResult,
)
from backend.services.adaptive_evacuation_service import get_adaptive_evacuation_service
from backend.services.feature_service import get_feature_service
from backend.services.forecast_service import get_forecast_service
from backend.services.ml_prediction_service import get_ml_prediction_service
from backend.services.resilience_scoring_service import get_resilience_scoring_service
from backend.services.risk_service import classify_risk_level
from backend.services.route_resilience_service import get_route_resilience_service
from backend.services.spatial_propagation_service import get_spatial_propagation_service


class ScenarioSimulationService:
    """Master engine for running and recording flood stress scenarios."""

    def __init__(self) -> None:
        self.feature_service = get_feature_service()
        self.forecast_service = get_forecast_service()
        self.ml_service = get_ml_prediction_service()
        self.spatial_service = get_spatial_propagation_service()
        self.adaptive_evac_service = get_adaptive_evacuation_service()
        self.route_resilience_service = get_route_resilience_service()
        self.resilience_service = get_resilience_scoring_service()

    def simulate(
        self,
        db: Session,
        name: str,
        rainfall_multiplier: float,
        horizon: str = "nowcast",
        simulation_demand_factor: float = 1.0,
        description: str | None = None,
        operator: str = "Command Center Operator",
    ) -> dict[str, Any]:
        """Execute full scenario simulation across all monitored sectors."""
        start_time = time.perf_counter()

        # Validate inputs
        if rainfall_multiplier <= 0.0 or rainfall_multiplier > 10.0:
            raise ValueError("Rainfall multiplier must be between 0.1x and 10.0x")
        if horizon not in ("nowcast", "6h", "12h", "24h"):
            raise ValueError(f"Invalid horizon '{horizon}'. Must be nowcast, 6h, 12h, or 24h.")
        if simulation_demand_factor <= 0.0 or simulation_demand_factor > 5.0:
            raise ValueError("Simulation demand factor must be between 0.1x and 5.0x")

        scenario_id = f"scen_{uuid.uuid4().hex[:12]}"
        grids = db.query(Grid).order_by(Grid.id.asc()).all()
        if not grids:
            raise RuntimeError("No monitored grids found in database.")

        # 1. Obtain baseline features & predictions for the requested horizon
        sector_predictions = self.forecast_service.predict_for_horizon(db, horizon)
        baseline_by_grid = {p["grid_id"]: p for p in sector_predictions}

        fdata = self.forecast_service.fetch_real_hourly_forecast()
        base_rainfall_mean = fdata.get_rainfall_for_horizon(horizon)
        sim_rainfall_mean = round(base_rainfall_mean * rainfall_multiplier, 2)

        # 2. Simulate sector predictions
        sector_results: list[dict[str, Any]] = []
        sectors_deteriorated = 0
        sectors_improved = 0
        sectors_critical = 0
        sectors_high = 0

        sim_sector_risks_lookup: dict[int, str] = {}

        for grid in grids:
            base_pred = baseline_by_grid.get(grid.id)
            if base_pred:
                base_prob = base_pred["probability"]
                base_risk = base_pred["risk_level"]
                features_dict = dict(base_pred.get("features", {}))
            else:
                feat_res = self.feature_service.build_features_for_grid(db, grid.id)
                features_dict = dict(feat_res.features)
                base_prob = 0.25
                base_risk = grid.flood_risk or "Low"

            # Modify ONLY rainfall features according to scenario
            rf_curr = min(1000.0, float(features_dict.get("rainfall_current_mm", 0.0)) * rainfall_multiplier)
            rf_3d = min(2500.0, float(features_dict.get("rainfall_3d_accum_mm", 0.0)) * rainfall_multiplier)
            rf_7d = min(5000.0, float(features_dict.get("rainfall_7d_accum_mm", 0.0)) * rainfall_multiplier)

            sim_features_dict = dict(features_dict)
            sim_features_dict["rainfall_current_mm"] = rf_curr
            sim_features_dict["rainfall_3d_accum_mm"] = rf_3d
            sim_features_dict["rainfall_7d_accum_mm"] = rf_7d

            # Reconstruct ordered feature vector for ML
            ordered_sim_vals = [
                sim_features_dict["rainfall_current_mm"],
                sim_features_dict["rainfall_3d_accum_mm"],
                sim_features_dict["rainfall_7d_accum_mm"],
                float(sim_features_dict.get("elevation_m", grid.elevation_m or 10.0)),
                float(sim_features_dict.get("distance_to_water_m", grid.distance_to_water or 500.0)),
                float(sim_features_dict.get("latitude", grid.latitude)),
                float(sim_features_dict.get("longitude", grid.longitude)),
                int(sim_features_dict.get("month", datetime.utcnow().month)),
            ]

            # Run inference using trained pipeline (or deterministic fallback)
            sim_pred = self.ml_service.predict_sector_risk(
                rainfall_current_mm=rf_curr,
                rainfall_3d_accum_mm=rf_3d,
                rainfall_7d_accum_mm=rf_7d,
                elevation_m=float(sim_features_dict.get("elevation_m", grid.elevation_m or 10.0)),
                distance_to_water_m=float(sim_features_dict.get("distance_to_water_m", grid.distance_to_water or 500.0)),
                latitude=float(sim_features_dict.get("latitude", grid.latitude)),
                longitude=float(sim_features_dict.get("longitude", grid.longitude)),
                month=int(sim_features_dict.get("month", datetime.utcnow().month)),
            )

            sim_prob = float(sim_pred["probability"])
            sim_risk = str(sim_pred["prediction"])

            prob_delta = round(sim_prob - base_prob, 4)
            is_trans = (sim_risk != base_risk)

            if is_trans:
                risk_order = {"Low": 1, "Moderate": 2, "High": 3, "Severe": 4}
                if risk_order.get(sim_risk, 0) > risk_order.get(base_risk, 0):
                    sectors_deteriorated += 1
                    transition_str = f"{base_risk} -> {sim_risk}"
                else:
                    sectors_improved += 1
                    transition_str = f"{base_risk} -> {sim_risk}"
            else:
                transition_str = "Stable"

            if sim_risk == "Severe":
                sectors_critical += 1
            elif sim_risk == "High":
                sectors_high += 1

            sim_sector_risks_lookup[grid.id] = sim_risk

            # Priority score formula
            p_score = min(1.0, 0.40 * sim_prob + 0.20 * max(0.0, prob_delta) + 0.15 * min(1.0, rf_curr / 150.0) + 0.25)
            if p_score >= 0.70 or sim_risk == "Severe":
                p_cat = "Critical"
            elif p_score >= 0.50 or sim_risk == "High":
                p_cat = "High"
            elif p_score >= 0.30:
                p_cat = "Medium"
            else:
                p_cat = "Low"

            sector_results.append({
                "grid_id": grid.id,
                "grid_name": grid.name,
                "baseline_probability": round(base_prob, 4),
                "simulated_probability": round(sim_prob, 4),
                "probability_delta": prob_delta,
                "baseline_risk": base_risk,
                "simulated_risk": sim_risk,
                "risk_transition": transition_str,
                "is_transitioned": is_trans,
                "priority_score": round(p_score, 4),
                "priority_category": p_cat,
                "features": sim_features_dict,
            })

        # Sort sector priority ranks
        sector_results.sort(key=lambda x: -x["priority_score"])
        for idx, sec in enumerate(sector_results, start=1):
            sec["priority_rank"] = idx

        # 3. Spatial risk propagation (Feature 2)
        spatial_analysis = self.spatial_service.analyze_propagation(db, sector_results)
        for sec in sector_results:
            sec["spatial_propagation_type"] = spatial_analysis.spatial_types_by_grid.get(sec["grid_id"], "UNAFFECTED")

        # 4. Shelter Capacity Stress Test (Feature 4)
        shelter_stress = self.adaptive_evac_service.evaluate_shelter_stress(
            db=db,
            simulated_sector_risks=sim_sector_risks_lookup,
            simulation_demand_factor=simulation_demand_factor,
        )
        shelters_stressed = sum(1 for s in shelter_stress if s["stress_status"] == "STRESSED")
        shelters_overloaded = sum(1 for s in shelter_stress if s["stress_status"] == "OVERLOADED")

        # 5. Adaptive Evacuation Route Resilience (Feature 3 & 5)
        # Evaluate routes for priority sectors (top 6 critical/high sectors)
        top_sectors = [s for s in sector_results if s["simulated_risk"] in ("Severe", "High")][:6]
        if not top_sectors:
            top_sectors = sector_results[:4]

        # Evacuation assignments
        evac_assignments = self.adaptive_evac_service.plan_evacuation_assignments(
            db=db,
            sector_results=sector_results,
            shelter_stress_results=shelter_stress,
        )
        assignments_lookup = {a["grid_id"]: a for a in evac_assignments}

        all_route_results: list[dict[str, Any]] = []
        routes_unsafe = 0
        routes_blocked = 0

        for sec in top_sectors:
            asgn = assignments_lookup.get(sec["grid_id"])
            if not asgn or not asgn["primary_shelter"]:
                continue
            prim_id = asgn["primary_shelter"]["id"]
            back_id = asgn["backup_shelter"]["id"] if asgn["backup_shelter"] else None

            routes = self.route_resilience_service.evaluate_route_alternatives(
                db=db,
                origin_grid_id=sec["grid_id"],
                primary_shelter_id=prim_id,
                backup_shelter_id=back_id,
                simulated_sector_risks=sim_sector_risks_lookup,
            )
            for r in routes:
                all_route_results.append(r)
                if r["route_status"] == "BLOCKED_BY_SIMULATION":
                    routes_blocked += 1
                elif r["route_status"] == "UNSAFE":
                    routes_unsafe += 1

        # 6. Resilience Scoring (Feature 6)
        resilience = self.resilience_service.compute_resilience(
            db=db,
            shelter_stress_results=shelter_stress,
            route_results=all_route_results,
        )

        execution_duration = (time.perf_counter() - start_time) * 1000.0

        # 7. Persist to database
        scenario_record = Scenario(
            id=scenario_id,
            name=name,
            description=description,
            rainfall_multiplier=rainfall_multiplier,
            horizon=horizon,
            simulation_demand_factor=simulation_demand_factor,
            baseline_rainfall_mm=base_rainfall_mean,
            simulated_rainfall_mm=sim_rainfall_mean,
            total_sectors=len(grids),
            sectors_deteriorated=sectors_deteriorated,
            sectors_improved=sectors_improved,
            sectors_critical=sectors_critical,
            sectors_high=sectors_high,
            shelters_stressed=shelters_stressed,
            shelters_overloaded=shelters_overloaded,
            routes_unsafe=routes_unsafe,
            routes_blocked=routes_blocked,
            system_resilience_score=resilience.overall,
            shelter_resilience_score=resilience.shelter,
            route_resilience_score=resilience.route,
            data_resilience_score=resilience.data,
            model_resilience_score=resilience.model,
            operational_resilience_score=resilience.operational,
            model_version=self.ml_service.model_version,
            is_fallback=not self.ml_service.is_available,
            execution_duration_ms=execution_duration,
            disclaimer="SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA",
        )
        db.add(scenario_record)
        db.flush()

        # Add sector records
        import json
        for sec in sector_results:
            sec_rec = ScenarioSectorResult(
                scenario_id=scenario_id,
                grid_id=sec["grid_id"],
                grid_name=sec["grid_name"],
                baseline_probability=sec["baseline_probability"],
                simulated_probability=sec["simulated_probability"],
                probability_delta=sec["probability_delta"],
                baseline_risk=sec["baseline_risk"],
                simulated_risk=sec["simulated_risk"],
                risk_transition=sec["risk_transition"],
                is_transitioned=sec["is_transitioned"],
                spatial_propagation_type=sec["spatial_propagation_type"],
                priority_score=sec["priority_score"],
                priority_rank=sec["priority_rank"],
                priority_category=sec["priority_category"],
                features_json=json.dumps(sec.get("features", {})),
            )
            db.add(sec_rec)

        # Add shelter records
        for sh in shelter_stress:
            sh_rec = ScenarioShelterResult(
                scenario_id=scenario_id,
                shelter_id=sh["shelter_id"],
                shelter_name=sh["shelter_name"],
                total_capacity=sh["total_capacity"],
                current_available_capacity=sh["current_available_capacity"],
                simulation_demand_factor=sh["simulation_demand_factor"],
                simulated_demand=sh["simulated_demand"],
                remaining_simulated_capacity=sh["remaining_simulated_capacity"],
                stress_status=sh["stress_status"],
                surrounding_flood_risk=sh["surrounding_flood_risk"],
                suitability_score=sh["suitability_score"],
                alternative_shelter_id=sh["alternative_shelter_id"],
            )
            db.add(sh_rec)

        # Add route records
        for rt in all_route_results:
            rt_rec = ScenarioRouteResult(
                scenario_id=scenario_id,
                origin_grid_id=rt["origin_grid_id"],
                destination_shelter_id=rt["destination_shelter_id"],
                route_role=rt["route_role"],
                distance_km=rt["distance_km"],
                duration_min=rt["duration_min"],
                baseline_hazard_score=rt["baseline_hazard_score"],
                simulated_hazard_score=rt["simulated_hazard_score"],
                simulated_peak_risk=rt["simulated_peak_risk"],
                high_risk_exposure_pct=rt["high_risk_exposure_pct"],
                severe_risk_exposure_pct=rt["severe_risk_exposure_pct"],
                route_status=rt["route_status"],
                advisory_message=rt["advisory_message"],
            )
            db.add(rt_rec)

        # Add resilience record
        res_rec = ResilienceAssessment(
            scenario_id=scenario_id,
            overall_resilience_score=resilience.overall,
            shelter_resilience_score=resilience.shelter,
            route_resilience_score=resilience.route,
            data_resilience_score=resilience.data,
            model_resilience_score=resilience.model,
            operational_resilience_score=resilience.operational,
            formula_version="v6.0.0",
            details_json=json.dumps(resilience.formula_breakdown),
        )
        db.add(res_rec)

        # Add decision audit log (Feature 10)
        audit_rec = DecisionAuditLog(
            scenario_id=scenario_id,
            event_type="SCENARIO_SIMULATION_EXECUTED",
            operator=operator,
            action_taken=f"Simulated flood stress: {name} ({rainfall_multiplier}x rainfall, {horizon} horizon)",
            parameters_json=json.dumps({
                "multiplier": rainfall_multiplier,
                "horizon": horizon,
                "demand_factor": simulation_demand_factor,
            }),
            impact_summary_json=json.dumps({
                "sectors_deteriorated": sectors_deteriorated,
                "critical_sectors": sectors_critical,
                "shelters_overloaded": shelters_overloaded,
                "routes_blocked": routes_blocked,
                "resilience_score": resilience.overall,
            }),
        )
        db.add(audit_rec)

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit scenario {scenario_id} to DB: {e}", exc_info=True)
            raise

        return {
            "scenario": scenario_record.to_dict(),
            "sectors": [s for s in sector_results],
            "shelters": shelter_stress,
            "routes": all_route_results,
            "spatial_propagation": spatial_analysis.to_dict(),
            "resilience": resilience.to_dict(),
            "evacuation_assignments": evac_assignments[:10],
            "disclaimer": "SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA",
        }


_scenario_sim_master: ScenarioSimulationService | None = None


def get_scenario_simulation_service() -> ScenarioSimulationService:
    global _scenario_sim_master
    if _scenario_sim_master is None:
        _scenario_sim_master = ScenarioSimulationService()
    return _scenario_sim_master
