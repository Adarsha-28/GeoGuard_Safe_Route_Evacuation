"""Route Resilience & Multi-Path Alternative Service for GeoGuard V6.

Evaluates route resilience under simulated flood scenarios:
- Primary Route, Alternative Route 1, Alternative Route 2.
- Point-by-point hazard exposure against simulated scenario risks.
- Route Status: 'AVAILABLE', 'CAUTION', 'UNSAFE', 'BLOCKED_BY_SIMULATION'.
- Explicit advisory disclaimer that 'BLOCKED_BY_SIMULATION' denotes simulated blockage.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.shelter import Shelter
from backend.services.routing_service import RoutingService
from backend.services.shelter_service import haversine_distance

RISK_WEIGHTS = {"Low": 0.0, "Moderate": 0.35, "High": 0.70, "Severe": 1.0}


class RouteResilienceService:
    """Evaluates multi-path route resilience and alternatives under simulated rainfall."""

    def __init__(self, routing_service: RoutingService | None = None) -> None:
        self.routing_service = routing_service or RoutingService()

    def evaluate_route_alternatives(
        self,
        db: Session,
        origin_grid_id: int,
        primary_shelter_id: int,
        backup_shelter_id: int | None,
        simulated_sector_risks: dict[int, str],  # grid_id -> simulated_risk
    ) -> list[dict[str, Any]]:
        """Evaluate Primary, Alternative 1, and Alternative 2 routes for a sector."""
        origin_grid = db.query(Grid).filter(Grid.id == origin_grid_id).first()
        primary_shelter = db.query(Shelter).filter(Shelter.id == primary_shelter_id).first()
        backup_shelter = db.query(Shelter).filter(Shelter.id == backup_shelter_id).first() if backup_shelter_id else None

        if not origin_grid or not primary_shelter:
            return []

        all_grids = db.query(Grid).all()

        routes_evaluated: list[dict[str, Any]] = []

        # 1. Primary Route: Direct route to primary shelter
        r_primary = self._evaluate_single_path(
            origin_grid=origin_grid,
            destination_shelter=primary_shelter,
            role="PRIMARY",
            waypoint=None,
            all_grids=all_grids,
            simulated_sector_risks=simulated_sector_risks,
        )
        routes_evaluated.append(r_primary)

        # 2. Alternative Route 1: Route to backup shelter (or alternative destination)
        alt1_dest = backup_shelter if backup_shelter else primary_shelter
        r_alt1 = self._evaluate_single_path(
            origin_grid=origin_grid,
            destination_shelter=alt1_dest,
            role="ALTERNATIVE_1",
            waypoint=None,
            all_grids=all_grids,
            simulated_sector_risks=simulated_sector_risks,
        )
        routes_evaluated.append(r_alt1)

        # 3. Alternative Route 2: Route via lateral waypoint avoiding direct line
        # Lateral offset point (+0.015 lat/lng perpendicular)
        lat_offset = (primary_shelter.latitude + origin_grid.latitude) / 2.0 + 0.015
        lng_offset = (primary_shelter.longitude + origin_grid.longitude) / 2.0 - 0.015
        r_alt2 = self._evaluate_single_path(
            origin_grid=origin_grid,
            destination_shelter=primary_shelter,
            role="ALTERNATIVE_2",
            waypoint=(lat_offset, lng_offset),
            all_grids=all_grids,
            simulated_sector_risks=simulated_sector_risks,
        )
        routes_evaluated.append(r_alt2)

        return routes_evaluated

    def _evaluate_single_path(
        self,
        origin_grid: Grid,
        destination_shelter: Shelter,
        role: str,
        waypoint: tuple[float, float] | None,
        all_grids: list[Grid],
        simulated_sector_risks: dict[int, str],
    ) -> dict[str, Any]:
        """Fetch path geometry, evaluate hazard exposure along trajectory, and assign status."""
        src_lat, src_lng = origin_grid.latitude, origin_grid.longitude
        dst_lat, dst_lng = destination_shelter.latitude, destination_shelter.longitude

        route_data = self.routing_service.fetch_osrm_route(
            src_lat=src_lat,
            src_lng=src_lng,
            dst_lat=dst_lat,
            dst_lng=dst_lng,
        )

        # Fallback straight-line trajectory
        if not route_data:
            direct_m = haversine_distance(src_lat, src_lng, dst_lat, dst_lng) * 1000.0
            factor = 1.25 if role != "ALTERNATIVE_2" else 1.5
            dist_meters = direct_m * factor
            duration_sec = dist_meters / 8.33  # ~30 km/h
            if waypoint:
                pts = [
                    [src_lng, src_lat],
                    [waypoint[1], waypoint[0]],
                    [dst_lng, dst_lat],
                ]
            else:
                pts = [
                    [src_lng, src_lat],
                    [(src_lng + dst_lng) / 2, (src_lat + dst_lat) / 2],
                    [dst_lng, dst_lat],
                ]
        else:
            dist_meters = float(route_data.get("distance", 0.0))
            duration_sec = float(route_data.get("duration", 0.0))
            pts = route_data.get("geometry", {}).get("coordinates", [])
            if not pts:
                pts = [[src_lng, src_lat], [dst_lng, dst_lat]]

        # Sample points along path to determine simulated risk exposure
        total_pts = max(1, len(pts))
        high_risk_pts = 0
        severe_risk_pts = 0
        sim_hazard_sum = 0.0
        base_hazard_sum = 0.0
        peak_risk = "Low"

        for pt in pts:
            pt_lng, pt_lat = pt[0], pt[1]
            # Find nearest grid sector
            closest_grid = None
            closest_d = float("inf")
            for g in all_grids:
                d = (g.latitude - pt_lat) ** 2 + (g.longitude - pt_lng) ** 2
                if d < closest_d:
                    closest_d = d
                    closest_grid = g

            if closest_grid:
                sim_risk = simulated_sector_risks.get(closest_grid.id, "Low")
                base_risk = closest_grid.flood_risk or "Low"
            else:
                sim_risk = "Low"
                base_risk = "Low"

            w_sim = RISK_WEIGHTS.get(sim_risk, 0.0)
            w_base = RISK_WEIGHTS.get(base_risk, 0.0)
            sim_hazard_sum += w_sim
            base_hazard_sum += w_base

            if sim_risk in ("High", "Severe"):
                high_risk_pts += 1
            if sim_risk == "Severe":
                severe_risk_pts += 1

            if sim_risk == "Severe":
                peak_risk = "Severe"
            elif sim_risk == "High" and peak_risk != "Severe":
                peak_risk = "High"
            elif sim_risk == "Moderate" and peak_risk not in ("High", "Severe"):
                peak_risk = "Moderate"

        high_exp_pct = (high_risk_pts / total_pts) * 100.0
        severe_exp_pct = (severe_risk_pts / total_pts) * 100.0
        avg_sim_hazard = sim_hazard_sum / total_pts
        avg_base_hazard = base_hazard_sum / total_pts

        # Determine route status
        if severe_exp_pct >= 35.0 or (avg_sim_hazard >= 0.75 and peak_risk == "Severe"):
            status = "BLOCKED_BY_SIMULATION"
            advisory = (
                f"Simulated inundation severely compromises route with {severe_exp_pct:.1f}% severe exposure. "
                "BLOCKED_BY_SIMULATION denotes a simulated hazard blockage, not an observed road closure."
            )
        elif avg_sim_hazard >= 0.50 or high_exp_pct >= 40.0:
            status = "UNSAFE"
            advisory = f"High hazard exposure ({high_exp_pct:.1f}%). Strongly consider alternative evacuation paths."
        elif peak_risk in ("Moderate", "High") or high_exp_pct >= 15.0:
            status = "CAUTION"
            advisory = f"Moderate water exposure along route ({high_exp_pct:.1f}%). Proceed with elevated caution."
        else:
            status = "AVAILABLE"
            advisory = "Clear path under simulated scenario with minimal flood hazard exposure."

        return {
            "origin_grid_id": origin_grid.id,
            "origin_grid_name": origin_grid.name,
            "destination_shelter_id": destination_shelter.id,
            "destination_shelter_name": destination_shelter.name,
            "route_role": role,
            "distance_km": round(dist_meters / 1000.0, 2),
            "duration_min": round(duration_sec / 60.0, 1),
            "baseline_hazard_score": round(avg_base_hazard, 4),
            "simulated_hazard_score": round(avg_sim_hazard, 4),
            "simulated_peak_risk": peak_risk,
            "high_risk_exposure_pct": round(high_exp_pct, 1),
            "severe_risk_exposure_pct": round(severe_exp_pct, 1),
            "route_status": status,
            "advisory_message": advisory,
        }


_route_resilience_instance: RouteResilienceService | None = None


def get_route_resilience_service() -> RouteResilienceService:
    global _route_resilience_instance
    if _route_resilience_instance is None:
        _route_resilience_instance = RouteResilienceService()
    return _route_resilience_instance
