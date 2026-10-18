"""Evacuation routing service integrating with OSRM and PostGIS hazard evaluation."""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy.orm import Session

from backend.config import HTTP_TIMEOUT, OSRM_URL, logger
from backend.services.risk_service import RiskService, get_risk_service
from backend.services.shelter_service import ShelterService, get_shelter_service, validate_coordinates


class RoutingService:
    """Service for querying road routes via OSRM and assessing flood risk exposure along paths."""

    def __init__(
        self,
        risk_service: RiskService | None = None,
        shelter_service: ShelterService | None = None,
        osrm_url: str | None = None,
        timeout: float = HTTP_TIMEOUT,
    ) -> None:
        self.risk_service = risk_service or get_risk_service()
        self.shelter_service = shelter_service or get_shelter_service()
        self.osrm_url = (osrm_url or OSRM_URL).rstrip("/")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._route_cache: dict[tuple[float, float, int], dict[str, Any]] = {}

    def fetch_osrm_route(
        self, src_lat: float, src_lng: float, dst_lat: float, dst_lng: float, retries: int = 1
    ) -> dict[str, Any] | None:
        """Query OSRM driving route between two points with timeout and retry."""
        url = (
            f"{self.osrm_url}/route/v1/driving/"
            f"{src_lng:.5f},{src_lat:.5f};{dst_lng:.5f},{dst_lat:.5f}"
            f"?overview=full&geometries=geojson"
        )
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "GeoGuard/2.0 Evacuation Routing Engine"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))

                if data.get("code") == "Ok" and data.get("routes"):
                    return data["routes"][0]
                else:
                    logger.warning(f"OSRM returned non-OK status: {data.get('code')}")
            except Exception as e:
                logger.warning(
                    f"OSRM route attempt {attempt + 1}/{retries + 1} failed for "
                    f"({src_lat}, {src_lng}) -> ({dst_lat}, {dst_lng}): {e}"
                )
        return None

    def evaluate_route_risk(
        self, db: Session, route: dict[str, Any], shelter: dict[str, Any]
    ) -> dict[str, Any]:
        """Assess flood hazard along route polyline coordinates and compute composite safety score."""
        geometry = route.get("geometry", {})
        distance_meters = float(route.get("distance", 0.0))
        duration_seconds = float(route.get("duration", 0.0))
        points = geometry.get("coordinates", [])

        total_points = len(points)
        high_severe_count = 0
        max_risk = "Low"

        # Sample points along path using PostGIS spatial query
        for pt in points:
            pt_lng, pt_lat = pt[0], pt[1]
            pt_risk = self.risk_service.query_risk_by_coordinate(db, pt_lat, pt_lng)
            if pt_risk in ("High", "Severe"):
                high_severe_count += 1
            if pt_risk == "Severe":
                max_risk = "Severe"
            elif pt_risk == "High" and max_risk != "Severe":
                max_risk = "High"
            elif pt_risk == "Moderate" and max_risk not in ("High", "Severe"):
                max_risk = "Moderate"

        shelter_risk = shelter.get("riskLevel", "Low")
        shelter_risk_penalty = (
            1.0 if shelter_risk == "Severe" else 0.8 if shelter_risk == "High" else 0.2 if shelter_risk == "Moderate" else 0.0
        )
        points_penalty = (high_severe_count / total_points) if total_points > 0 else 0.0
        combined_risk = max(points_penalty, shelter_risk_penalty)
        safety_score = round(max(0.0, 1.0 - combined_risk), 4)

        dist_km = round(distance_meters / 1000.0, 2)
        duration_mins = round(duration_seconds / 60.0, 1)

        # Higher is better: 1 / (1 + x)
        distance_score = 1.0 / (1.0 + dist_km)
        time_score = 1.0 / (1.0 + duration_mins)

        # Composite Route Score: Safety 50%, Distance 30%, Time 20%
        route_score = round(
            (0.5 * safety_score) + (0.3 * distance_score) + (0.2 * time_score), 4
        )

        reason = "Selected because it offers minimal flood hazard exposure to an active shelter."
        if shelter_risk in ("High", "Severe"):
            reason = f"Warning: Target shelter is in a {shelter_risk.lower()} risk zone, but path is the safest accessible option."
        elif high_severe_count > 0:
            reason = "Route briefly traverses areas near moderate/high risk but provides the safest overall trajectory."

        safety_rating = (
            "Excellent" if safety_score >= 0.85
            else "Good" if safety_score >= 0.60
            else "Caution" if safety_score >= 0.40
            else "Hazardous"
        )

        logger.info(
            f"route_evaluation: evaluated path to shelter '{shelter.get('name')}' "
            f"(dist={dist_km}km, safety={safety_score}, hazard_points={high_severe_count}/{total_points})"
        )

        return {
            "distance": distance_meters,
            "dist_km": dist_km,
            "duration": duration_seconds,
            "duration_mins": duration_mins,
            "riskScore": round(float(combined_risk), 4),
            "safetyScore": float(safety_score),
            "safetyRating": safety_rating,
            "maxRisk": max_risk,
            "hazard_points_count": high_severe_count,
            "predicted_flood_hazard_points": high_severe_count,
            "confirmed_road_closures": 0,
            "hazard_distinction": "Predicted flood-risk area based on V4 operational intelligence (advisory support; roads are not automatically blocked without official closure reports)",
            "total_points": total_points,
            "score": route_score,
            "reason": reason,
            "geometry": geometry,
        }

    def calculate_safest_evacuation_route(
        self, db: Session, lat: float, lng: float, top_shelter_candidates: int = 3
    ) -> dict[str, Any]:
        """Find the safest evacuation path from starting point to best accessible relief shelter."""
        is_valid, err = validate_coordinates(lat, lng)
        if not is_valid:
            raise ValueError(err)

        # 1. Fetch nearest active shelters with available capacity via PostGIS
        nearby_shelters = self.shelter_service.find_nearby_shelters(
            db, lat, lng, radius_km=30.0, limit=top_shelter_candidates, available_only=True
        )

        if not nearby_shelters:
            raise RuntimeError("No active shelters with available capacity found within range.")

        candidate_routes: list[dict[str, Any]] = []

        for s in nearby_shelters:
            osrm_route = self.fetch_osrm_route(lat, lng, s["latitude"], s["longitude"])
            if not osrm_route:
                continue

            eval_result = self.evaluate_route_risk(db, osrm_route, s)
            route_data = {
                "distance": eval_result["distance"],
                "dist_km": eval_result["dist_km"],
                "duration": eval_result["duration"],
                "duration_mins": eval_result["duration_mins"],
                "riskScore": eval_result["riskScore"],
                "safetyScore": eval_result["safetyScore"],
                "maxRisk": eval_result["maxRisk"],
                "geometry": eval_result["geometry"],
            }

            candidate_routes.append({
                "shelter": s,
                "route": route_data,
                "score": eval_result["score"],
                "reason": eval_result["reason"],
            })

        if not candidate_routes:
            raise RuntimeError("Unable to communicate with routing service to compute route.")

        # Sort candidate routes by highest composite score
        candidate_routes.sort(key=lambda x: x["score"], reverse=True)
        return candidate_routes[0]


_singleton_routing_service: RoutingService | None = None


def get_routing_service() -> RoutingService:
    """Retrieve singleton instance of RoutingService."""
    global _singleton_routing_service
    if _singleton_routing_service is None:
        _singleton_routing_service = RoutingService()
    return _singleton_routing_service
