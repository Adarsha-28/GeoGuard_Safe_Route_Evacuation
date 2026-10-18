"""Zone Prioritization Engine for GeoGuard V5.

Calculates an empirical operational triage prioritization score for Chennai sectors:
1. Predicted Flood Probability (40% weight)
2. Risk Deterioration Velocity (Probability Delta) (20% weight)
3. Cumulative Rainfall Hazard (15% weight)
4. Shelter Accessibility Deficit (15% weight)
5. Model Confidence (10% weight)

* Population data is not empirically available per grid sector in the open-source dataset,
  and per system safety rules, synthetic demographics are strictly omitted rather than manufactured.

Categorizes sectors into: 'Critical', 'High', 'Medium', 'Low'.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.shelter import Shelter
from backend.models.zone_priority import ZonePriority
from backend.services.forecast_service import ForecastService, get_forecast_service
from backend.services.risk_trend_service import RiskTrendService, get_risk_trend_service
from backend.services.shelter_service import ShelterService, get_shelter_service

PRIORITY_CATEGORY_THRESHOLDS = {
    "Critical": 0.70,
    "High": 0.50,
    "Medium": 0.30,
    # Below 0.30 is "Low"
}


class PriorityService:
    """Calculates operational triage priority ranking across Chennai monitored sectors."""

    def __init__(
        self,
        forecast_service: ForecastService | None = None,
        risk_trend_service: RiskTrendService | None = None,
        shelter_service: ShelterService | None = None,
    ) -> None:
        self.forecast_service = forecast_service or get_forecast_service()
        self.risk_trend_service = risk_trend_service or get_risk_trend_service()
        self.shelter_service = shelter_service or get_shelter_service()

    def calculate_priorities(
        self,
        db: Session,
        horizon: str = "nowcast",
        persist: bool = True,
    ) -> list[dict[str, Any]]:
        """Compute operational priority scores and ranks for all Chennai sectors."""
        predictions = self.forecast_service.predict_for_horizon(db, horizon=horizon)
        if not predictions:
            return []

        # Get active shelters for accessibility calculation
        active_shelters = db.query(Shelter).filter(Shelter.is_active == True).all()

        now_dt = datetime.utcnow()
        scored_sectors = []

        for p in predictions:
            grid_id = int(p["grid_id"])
            prob = float(p["probability"])
            risk_level = str(p["risk_level"])
            confidence = float(p["confidence"])
            rain_mm = float(p["rainfall_mm"])
            rain_3d = float(p["rainfall_3d_mm"])

            # 1. Probability component (0.0 - 1.0)
            comp_prob = prob

            # 2. Deterioration delta component
            # Query recent delta from risk trends
            trend_data = self.risk_trend_service.get_grid_risk_trends(db, grid_id=grid_id, hours=6, horizon=horizon)
            prob_delta = float(trend_data.get("overall_probability_delta", 0.0))
            # Deterioration is positive delta (scaled to [0.0, 1.0])
            comp_delta = max(0.0, min(1.0, prob_delta * 2.0))

            # 3. Rainfall accumulation component (max 150mm threshold)
            comp_rain = min(1.0, (rain_mm * 0.5 + rain_3d * 0.5) / 100.0)

            # 4. Shelter accessibility deficit (distance to nearest shelter with available capacity)
            # Find nearest shelter with available capacity
            min_dist_km = 999.0
            for s in active_shelters:
                if s.available_capacity > 0:
                    d = ((s.latitude - p["features"]["latitude"]) ** 2 + (s.longitude - p["features"]["longitude"]) ** 2) ** 0.5 * 111.0
                    if d < min_dist_km:
                        min_dist_km = d
            # Deficit: 0 if shelter is close (<= 1 km), 1.0 if far (>= 10 km)
            comp_shelter_deficit = min(1.0, max(0.0, (min_dist_km - 1.0) / 9.0))
            shelter_access_score = round(1.0 - comp_shelter_deficit, 4)

            # 5. Confidence weight
            comp_confidence = confidence

            # Composite Score:
            # 40% probability + 20% deterioration + 15% rainfall + 15% shelter deficit + 10% confidence
            priority_score = (
                (0.40 * comp_prob)
                + (0.20 * comp_delta)
                + (0.15 * comp_rain)
                + (0.15 * comp_shelter_deficit)
                + (0.10 * comp_confidence)
            )
            priority_score = round(max(0.0, min(1.0, priority_score)), 4)

            # Categorize
            if priority_score >= PRIORITY_CATEGORY_THRESHOLDS["Critical"]:
                category = "Critical"
            elif priority_score >= PRIORITY_CATEGORY_THRESHOLDS["High"]:
                category = "High"
            elif priority_score >= PRIORITY_CATEGORY_THRESHOLDS["Medium"]:
                category = "Medium"
            else:
                category = "Low"

            scored_sectors.append({
                "grid_id": grid_id,
                "grid_name": p["grid_name"],
                "priority_score": priority_score,
                "priority_category": category,
                "risk_level": risk_level,
                "predicted_probability": prob,
                "probability_delta": round(prob_delta, 4),
                "rainfall_accumulation_mm": round(rain_mm + rain_3d, 2),
                "shelter_accessibility_score": shelter_access_score,
                "confidence": confidence,
                "horizon": horizon,
                "calculated_at": now_dt.isoformat() + "Z",
                "recommended_action": (
                    "Deploy emergency resources and pre-position evacuation support." if category == "Critical"
                    else "High readiness: verify route accessibility and notify local shelters." if category == "High"
                    else "Monitor conditions closely for rapid deterioration." if category == "Medium"
                    else "Routine monitoring; baseline operational posture."
                ),
            })

        # Sort descending by priority score and assign rank
        scored_sectors.sort(key=lambda x: x["priority_score"], reverse=True)
        for rank, item in enumerate(scored_sectors, start=1):
            item["priority_rank"] = rank

        # Persist into database if requested
        if persist:
            for item in scored_sectors:
                existing = db.query(ZonePriority).filter(ZonePriority.grid_id == item["grid_id"]).first()
                if existing:
                    existing.priority_score = item["priority_score"]
                    existing.priority_rank = item["priority_rank"]
                    existing.priority_category = item["priority_category"]
                    existing.risk_level = item["risk_level"]
                    existing.predicted_probability = item["predicted_probability"]
                    existing.probability_delta = item["probability_delta"]
                    existing.rainfall_accumulation_mm = item["rainfall_accumulation_mm"]
                    existing.shelter_accessibility_score = item["shelter_accessibility_score"]
                    existing.confidence = item["confidence"]
                    existing.calculated_at = now_dt
                else:
                    new_zp = ZonePriority(
                        grid_id=item["grid_id"],
                        priority_score=item["priority_score"],
                        priority_rank=item["priority_rank"],
                        priority_category=item["priority_category"],
                        risk_level=item["risk_level"],
                        predicted_probability=item["predicted_probability"],
                        probability_delta=item["probability_delta"],
                        rainfall_accumulation_mm=item["rainfall_accumulation_mm"],
                        shelter_accessibility_score=item["shelter_accessibility_score"],
                        confidence=item["confidence"],
                        calculated_at=now_dt,
                    )
                    db.add(new_zp)

        return scored_sectors


_singleton_priority_service: PriorityService | None = None


def get_priority_service() -> PriorityService:
    """Retrieve singleton instance of PriorityService."""
    global _singleton_priority_service
    if _singleton_priority_service is None:
        _singleton_priority_service = PriorityService()
    return _singleton_priority_service
