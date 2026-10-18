"""Shelter Intelligence Service for GeoGuard V5.

Assesses relief shelters based on live operational factors:
1. Current capacity & available capacity
2. Surrounding flood risk (using PostGIS spatial containment/proximity to grid sectors)
3. Shelter suitability score (capacity headroom + flood hazard safety)
4. Operational warning status ('Optimal', 'Available', 'At Capacity', 'Surrounding Risk Elevated', 'Severe Risk Zone')
5. Prioritization ranking without decrementing capacity automatically.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.shelter import Shelter
from backend.services.risk_service import RiskService, get_risk_service
from backend.services.shelter_service import ShelterService, get_shelter_service, haversine_distance


class ShelterIntelligenceService:
    """Provides decision-support intelligence on relief shelter suitability and risks."""

    def __init__(
        self,
        shelter_service: ShelterService | None = None,
        risk_service: RiskService | None = None,
    ) -> None:
        self.shelter_service = shelter_service or get_shelter_service()
        self.risk_service = risk_service or get_risk_service()

    def evaluate_shelters_intelligence(
        self,
        db: Session,
        user_lat: float | None = None,
        user_lng: float | None = None,
        radius_km: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Evaluate all active relief shelters and compute operational suitability scores."""
        shelters = db.query(Shelter).filter(Shelter.is_active == True).all()
        if not shelters:
            return []

        # Query surrounding grid risk for each shelter using PostGIS spatial containment or nearest grid
        evaluated_shelters = []

        for s in shelters:
            # 1. Surrounding flood risk
            surrounding_risk = self.risk_service.query_risk_by_coordinate(db, s.latitude, s.longitude)
            # Default to shelter.risk_level if query returns None
            surrounding_risk = surrounding_risk or s.risk_level or "Low"

            # 2. Capacity ratio
            cap = max(1, s.capacity)
            avail = max(0, s.available_capacity)
            capacity_ratio = avail / float(cap)

            # 3. Distance from operator/user if provided
            distance_km = None
            if user_lat is not None and user_lng is not None:
                distance_km = haversine_distance(user_lat, user_lng, s.latitude, s.longitude)

            # 4. Risk penalty
            risk_penalty = {
                "Low": 0.0,
                "Moderate": 0.25,
                "High": 0.65,
                "Severe": 1.0,
            }.get(surrounding_risk, 0.25)

            # 5. Suitability score [0.0 - 1.0]
            # Higher is better: combination of capacity headroom (60%) and environmental safety (40%)
            # If distance is known, incorporate proximity factor
            if distance_km is not None:
                dist_factor = 1.0 / (1.0 + (distance_km / 10.0))
                suitability = (0.40 * capacity_ratio) + (0.40 * (1.0 - risk_penalty)) + (0.20 * dist_factor)
            else:
                suitability = (0.55 * capacity_ratio) + (0.45 * (1.0 - risk_penalty))

            suitability = round(max(0.0, min(1.0, suitability)), 4)

            # 6. Operational warning status
            if surrounding_risk == "Severe":
                warning_status = "Severe Risk Zone"
                recommendation = "Do not route evacuees here: surrounding area is experiencing critical inundation hazard."
            elif avail <= 0:
                warning_status = "At Capacity"
                recommendation = "Facility is full. Evacuation requests must be redirected to next nearest shelter."
            elif surrounding_risk == "High":
                warning_status = "Surrounding Risk Elevated"
                recommendation = "Caution: high water levels nearby. Prepare alternate facility if conditions worsen."
            elif capacity_ratio >= 0.50 and surrounding_risk == "Low":
                warning_status = "Optimal"
                recommendation = "Primary recommended facility: ample capacity in safe high-ground sector."
            else:
                warning_status = "Available"
                recommendation = "Operational facility with open capacity."


            evaluated_shelters.append({
                "id": s.id,
                "name": s.name,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "address": s.address,
                "capacity": s.capacity,
                "available_capacity": s.available_capacity,
                "capacity_utilization_pct": round(((cap - avail) / cap) * 100.0, 1),
                "surrounding_flood_risk": surrounding_risk,
                "suitability_score": suitability,
                "warning_status": warning_status,
                "recommendation": recommendation,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "facilities": s.facilities,
                "contact": s.contact,
                "is_active": s.is_active,
            })

        # Filter by radius if user position provided
        if user_lat is not None and user_lng is not None:
            evaluated_shelters = [
                s for s in evaluated_shelters
                if s["distance_km"] is None or s["distance_km"] <= radius_km
            ]

        # Prioritize: Highest suitability first
        evaluated_shelters.sort(key=lambda x: x["suitability_score"], reverse=True)
        return evaluated_shelters


_singleton_shelter_intelligence: ShelterIntelligenceService | None = None


def get_shelter_intelligence_service() -> ShelterIntelligenceService:
    """Retrieve singleton instance of ShelterIntelligenceService."""
    global _singleton_shelter_intelligence
    if _singleton_intelligence := _singleton_shelter_intelligence:
        return _singleton_intelligence
    _singleton_shelter_intelligence = ShelterIntelligenceService()
    return _singleton_shelter_intelligence
