"""Route Intelligence Service for GeoGuard V5.

Enhances OSRM + PostGIS evacuation route evaluation:
- Distance & Duration
- Maximum flood risk encountered along trajectory
- Average route risk exposure
- Percentage of path traversing elevated hazard zones
- Composite route safety score
- Status Classification: 'Recommended', 'Caution', 'Unsafe'
- Strictly advisory decision support terminology.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.shelter import Shelter
from backend.services.risk_service import RiskService, get_risk_service
from backend.services.routing_service import RoutingService
from backend.services.shelter_service import ShelterService, get_shelter_service, validate_coordinates

RISK_WEIGHTS = {"Low": 0.0, "Moderate": 0.35, "High": 0.70, "Severe": 1.0}


class RouteIntelligenceService:
    """Calculates comprehensive route hazard intelligence for candidate evacuation paths."""

    def __init__(
        self,
        routing_service: RoutingService | None = None,
        risk_service: RiskService | None = None,
        shelter_service: ShelterService | None = None,
    ) -> None:
        self.routing_service = routing_service or RoutingService()
        self.risk_service = risk_service or get_risk_service()
        self.shelter_service = shelter_service or get_shelter_service()

    def evaluate_route_intelligence(
        self,
        db: Session,
        src_lat: float,
        src_lng: float,
        shelter_id: int,
    ) -> dict[str, Any]:
        """Evaluate detailed flood hazard exposure along an OSRM path to a designated shelter."""
        valid, err = validate_coordinates(src_lat, src_lng)
        if not valid:
            raise ValueError(err)

        shelter = db.query(Shelter).filter(Shelter.id == shelter_id).first()
        if not shelter:
            raise ValueError(f"Shelter {shelter_id} not found.")

        # 1. Fetch OSRM driving route
        route = self.routing_service.fetch_osrm_route(
            src_lat=src_lat,
            src_lng=src_lng,
            dst_lat=shelter.latitude,
            dst_lng=shelter.longitude,
        )

        # Fallback straight-line if OSRM is unreachable
        if not route:
            logger.warning(f"OSRM unavailable for ({src_lat}, {src_lng}) -> shelter {shelter_id}. Using geometric evaluation.")
            dist_meters = ((shelter.latitude - src_lat) ** 2 + (shelter.longitude - src_lng) ** 2) ** 0.5 * 111000.0
            route = {
                "distance": dist_meters,
                "duration": dist_meters / 8.33,  # ~30 km/h
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [src_lng, src_lat],
                        [(src_lng + shelter.longitude) / 2, (src_lat + shelter.latitude) / 2],
                        [shelter.longitude, shelter.latitude],
                    ],
                },
            }

        distance_meters = float(route.get("distance", 0.0))
        duration_seconds = float(route.get("duration", 0.0))
        points = route.get("geometry", {}).get("coordinates", [])
        total_points = max(1, len(points))

        # 2. Sample points along trajectory
        max_risk = "Low"
        point_risks = []
        risky_points_count = 0  # Moderate, High, Severe

        for pt in points:
            pt_lng, pt_lat = pt[0], pt[1]
            pt_risk = self.risk_service.query_risk_by_coordinate(db, pt_lat, pt_lng) or "Low"
            point_risks.append(pt_risk)

            if pt_risk in ("Moderate", "High", "Severe"):
                risky_points_count += 1

            if pt_risk == "Severe":
                max_risk = "Severe"
            elif pt_risk == "High" and max_risk != "Severe":
                max_risk = "High"
            elif pt_risk == "Moderate" and max_risk not in ("High", "Severe"):
                max_risk = "Moderate"

        # 3. Calculate statistics
        percent_risky = round((risky_points_count / float(total_points)) * 100.0, 1)
        avg_risk_score = round(
            sum(RISK_WEIGHTS.get(r, 0.0) for r in point_risks) / float(total_points), 4
        )

        # Shelter risk penalty
        surrounding_risk = self.risk_service.query_risk_by_coordinate(db, shelter.latitude, shelter.longitude) or shelter.risk_level or "Low"
        shelter_penalty = RISK_WEIGHTS.get(surrounding_risk, 0.25)

        # Composite Safety Score: 1.0 - (0.6 * avg_risk + 0.4 * shelter_penalty)
        composite_hazard = (0.60 * avg_risk_score) + (0.40 * shelter_penalty)
        safety_score = round(max(0.0, min(1.0, 1.0 - composite_hazard)), 4)

        # 4. Status Classification
        if max_risk == "Severe" or safety_score < 0.45 or shelter.available_capacity <= 0:
            status = "Unsafe"
            advisory_text = (
                "ADVISORY: Path traverses severe flood hazard zones or target facility is at capacity. "
                "Do not dispatch evacuees along this trajectory without field verification."
            )
        elif max_risk == "High" or safety_score < 0.70:
            status = "Caution"
            advisory_text = (
                "ADVISORY: Route encounters elevated flood hazards. Proceed with high caution and monitor water depths."
            )
        else:
            status = "Recommended"
            advisory_text = (
                "ADVISORY: Modeled trajectory presents minimal flood hazard exposure. Preferred evacuation corridor."
            )

        dist_km = round(distance_meters / 1000.0, 2)
        dur_mins = round(duration_seconds / 60.0, 1)

        return {
            "shelter_id": shelter.id,
            "shelter_name": shelter.name,
            "shelter_available_capacity": shelter.available_capacity,
            "shelter_surrounding_risk": surrounding_risk,
            "source": {"latitude": src_lat, "longitude": src_lng},
            "destination": {"latitude": shelter.latitude, "longitude": shelter.longitude},
            "distance_meters": distance_meters,
            "distance_km": dist_km,
            "duration_seconds": duration_seconds,
            "duration_minutes": dur_mins,
            "maximum_flood_risk": max_risk,
            "average_route_risk": avg_risk_score,
            "percent_route_in_risky_zones": percent_risky,
            "safety_score": safety_score,
            "status": status,
            "advisory_disclaimer": (
                "Decision Support Advisory: Flood assessments are mathematical models based on available precipitation "
                "and elevation data. Local street blockages and flash flooding must be verified by local incident commanders."
            ),
            "advisory_text": advisory_text,
            "geometry": route.get("geometry"),
        }


_singleton_route_intelligence: RouteIntelligenceService | None = None


def get_route_intelligence_service() -> RouteIntelligenceService:
    """Retrieve singleton instance of RouteIntelligenceService."""
    global _singleton_route_intelligence
    if _singleton_route_intelligence is None:
        _singleton_route_intelligence = RouteIntelligenceService()
    return _singleton_route_intelligence
