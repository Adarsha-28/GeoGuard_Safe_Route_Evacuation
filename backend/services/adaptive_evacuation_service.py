"""Adaptive Evacuation & Shelter Stress Service for GeoGuard V6.

Evaluates shelter capacity stress and adaptive evacuation assignments:
- Simulation Demand Factors: 1.0x, 1.25x, 1.5x, 2.0x (without inventing population stats).
- Categorizes shelter stress: 'NORMAL', 'STRESSED', 'OVERLOADED'.
- Computes shelter suitability based on capacity headroom and surrounding flood risk.
- Identifies backup shelters and alternative relief facilities with surplus headroom.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.shelter import Shelter
from backend.services.shelter_service import haversine_distance


class AdaptiveEvacuationService:
    """Evaluates shelter network stress and adaptive evacuation routing."""

    def evaluate_shelter_stress(
        self,
        db: Session,
        simulated_sector_risks: dict[int, str],  # grid_id -> simulated_risk
        simulation_demand_factor: float = 1.0,
    ) -> list[dict[str, Any]]:
        """Stress-test all relief shelters under the requested simulation demand factor."""
        shelters = db.query(Shelter).filter(Shelter.is_active == True).all()  # noqa: E712
        grids = db.query(Grid).all()

        shelter_results: list[dict[str, Any]] = []

        # Find closest grid sector for each shelter to evaluate surrounding flood risk
        grid_lookup = {g.id: g for g in grids}

        for s in shelters:
            # 1. Determine surrounding sector risk
            surrounding_risk = "Low"
            closest_dist = float("inf")
            for g in grids:
                d = haversine_distance(s.latitude, s.longitude, g.latitude, g.longitude)
                if d < closest_dist:
                    closest_dist = d
                    surrounding_risk = simulated_sector_risks.get(g.id, "Low")

            # 2. Compute simulated demand based strictly on capacity headroom and demand factor
            # Baseline utilized capacity
            baseline_occupied = max(0, s.capacity - s.available_capacity)
            if baseline_occupied == 0:
                # Nominal planning allocation ~40% of capacity
                baseline_occupied = int(s.capacity * 0.40)

            simulated_demand = int(baseline_occupied * simulation_demand_factor)
            remaining_cap = s.capacity - simulated_demand

            # 3. Categorize stress status
            headroom_ratio = remaining_cap / max(1, s.capacity)
            if remaining_cap < 0:
                stress_status = "OVERLOADED"
            elif headroom_ratio < 0.25:
                stress_status = "STRESSED"
            else:
                stress_status = "NORMAL"

            # 4. Calculate suitability score (0.0 to 1.0)
            risk_penalty = {
                "Low": 0.0,
                "Moderate": 0.2,
                "High": 0.5,
                "Severe": 0.85,
            }.get(surrounding_risk, 0.0)

            clamped_headroom = max(0.0, min(1.0, headroom_ratio))
            suitability = round(clamped_headroom * (1.0 - risk_penalty), 3)

            shelter_results.append({
                "shelter_id": s.id,
                "shelter_name": s.name,
                "total_capacity": s.capacity,
                "current_available_capacity": s.available_capacity,
                "simulation_demand_factor": simulation_demand_factor,
                "simulated_demand": simulated_demand,
                "remaining_simulated_capacity": remaining_cap,
                "stress_status": stress_status,
                "surrounding_flood_risk": surrounding_risk,
                "suitability_score": suitability,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "alternative_shelter_id": None,
                "alternative_shelter_name": None,
            })

        # 5. Assign alternative shelters for STRESSED or OVERLOADED shelters
        normal_shelters = [
            sh for sh in shelter_results
            if sh["stress_status"] == "NORMAL" and sh["surrounding_flood_risk"] in ("Low", "Moderate")
        ]
        if not normal_shelters:
            normal_shelters = [sh for sh in shelter_results if sh["remaining_simulated_capacity"] > 0]

        for sh in shelter_results:
            if sh["stress_status"] in ("STRESSED", "OVERLOADED") and normal_shelters:
                # Find nearest normal shelter with spare headroom
                best_alt = None
                best_dist = float("inf")
                for alt in normal_shelters:
                    if alt["shelter_id"] == sh["shelter_id"]:
                        continue
                    dist = haversine_distance(sh["latitude"], sh["longitude"], alt["latitude"], alt["longitude"])
                    if dist < best_dist:
                        best_dist = dist
                        best_alt = alt

                if best_alt:
                    sh["alternative_shelter_id"] = best_alt["shelter_id"]
                    sh["alternative_shelter_name"] = best_alt["shelter_name"]

        return shelter_results

    def plan_evacuation_assignments(
        self,
        db: Session,
        sector_results: list[dict[str, Any]],
        shelter_stress_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate priority sectors with primary & backup shelter recommendations."""
        grids = {g.id: g for g in db.query(Grid).all()}
        shelters_by_id = {s["shelter_id"]: s for s in shelter_stress_results}

        assignments: list[dict[str, Any]] = []

        # Sort sectors by simulated priority / risk
        sorted_sectors = sorted(
            sector_results,
            key=lambda x: (
                {"Severe": 4, "High": 3, "Moderate": 2, "Low": 1}.get(x["simulated_risk"], 0),
                x.get("probability_delta", 0.0),
            ),
            reverse=True,
        )

        for sec in sorted_sectors:
            gid = sec["grid_id"]
            grid = grids.get(gid)
            if not grid:
                continue

            # Find primary and backup shelter based on proximity and suitability
            candidate_shelters = sorted(
                shelter_stress_results,
                key=lambda sh: (
                    haversine_distance(grid.latitude, grid.longitude, sh["latitude"], sh["longitude"]),
                    -sh["suitability_score"],
                ),
            )

            primary_shelter = candidate_shelters[0] if candidate_shelters else None
            # Backup shelter: second candidate or alternative
            backup_shelter = None
            for cand in candidate_shelters[1:]:
                if cand["stress_status"] != "OVERLOADED":
                    backup_shelter = cand
                    break
            if not backup_shelter and len(candidate_shelters) > 1:
                backup_shelter = candidate_shelters[1]

            assignments.append({
                "grid_id": gid,
                "grid_name": sec["grid_name"],
                "simulated_risk": sec["simulated_risk"],
                "simulated_probability": sec["simulated_probability"],
                "priority_category": sec["priority_category"],
                "primary_shelter": {
                    "id": primary_shelter["shelter_id"] if primary_shelter else None,
                    "name": primary_shelter["shelter_name"] if primary_shelter else None,
                    "stress_status": primary_shelter["stress_status"] if primary_shelter else "UNKNOWN",
                    "remaining_capacity": primary_shelter["remaining_simulated_capacity"] if primary_shelter else 0,
                    "distance_km": round(haversine_distance(grid.latitude, grid.longitude, primary_shelter["latitude"], primary_shelter["longitude"]), 2) if primary_shelter else 0.0,
                } if primary_shelter else None,
                "backup_shelter": {
                    "id": backup_shelter["shelter_id"] if backup_shelter else None,
                    "name": backup_shelter["shelter_name"] if backup_shelter else None,
                    "stress_status": backup_shelter["stress_status"] if backup_shelter else "UNKNOWN",
                    "remaining_capacity": backup_shelter["remaining_simulated_capacity"] if backup_shelter else 0,
                    "distance_km": round(haversine_distance(grid.latitude, grid.longitude, backup_shelter["latitude"], backup_shelter["longitude"]), 2) if backup_shelter else 0.0,
                } if backup_shelter else None,
            })

        return assignments


_adaptive_evac_instance: AdaptiveEvacuationService | None = None


def get_adaptive_evacuation_service() -> AdaptiveEvacuationService:
    global _adaptive_evac_instance
    if _adaptive_evac_instance is None:
        _adaptive_evac_instance = AdaptiveEvacuationService()
    return _adaptive_evac_instance
