"""Temporal Intelligence and Prediction Delta Engine for GeoGuard V5.

Tracks historical predictions across cycles, performs cycle-over-cycle delta analysis,
detects risk trends ('DETERIORATING', 'IMPROVING', 'STABLE', 'SUDDEN_DETERIORATION', 'RECOVERY_DETECTED'),
and persists historical state snapshots into PostgreSQL.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.prediction_history import PredictionHistory
from backend.models.risk_transition import RiskTransitionRecord

RISK_RANK = {"Low": 0, "Moderate": 1, "High": 2, "Severe": 3}


class PredictionDelta:
    """Represents cycle-over-cycle change for a grid sector."""

    def __init__(
        self,
        grid_id: int,
        grid_name: str,
        previous_probability: float | None,
        current_probability: float,
        probability_delta: float,
        previous_level: str | None,
        current_level: str,
        trend: str,
        rainfall_delta: float = 0.0,
        confidence_delta: float = 0.0,
        horizon: str = "nowcast",
    ) -> None:
        self.grid_id = grid_id
        self.grid_name = grid_name
        self.previous_probability = round(previous_probability, 4) if previous_probability is not None else None
        self.current_probability = round(current_probability, 4)
        self.probability_delta = round(probability_delta, 4)
        self.previous_level = previous_level
        self.current_level = current_level
        self.trend = trend
        self.rainfall_delta = round(rainfall_delta, 2)
        self.confidence_delta = round(confidence_delta, 4)
        self.horizon = horizon

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_id": self.grid_id,
            "grid_name": self.grid_name,
            "previous_probability": self.previous_probability,
            "current_probability": self.current_probability,
            "probability_delta": self.probability_delta,
            "previous_level": self.previous_level,
            "current_level": self.current_level,
            "trend": self.trend,
            "rainfall_delta": self.rainfall_delta,
            "confidence_delta": self.confidence_delta,
            "horizon": self.horizon,
        }


class RiskTrendService:
    """Manages historical risk tracking, delta evaluation, and trend intelligence."""

    @staticmethod
    def classify_trend(
        prev_level: str | None,
        curr_level: str,
        prev_prob: float | None,
        curr_prob: float,
    ) -> str:
        """Classify directional trend based on risk levels and probability delta."""
        if prev_level is None or prev_prob is None:
            return "STABLE"

        prev_r = RISK_RANK.get(prev_level, 0)
        curr_r = RISK_RANK.get(curr_level, 0)
        prob_delta = curr_prob - prev_prob

        # Sudden deterioration: jump >= 2 levels, or probability surge >= +0.35
        if (curr_r - prev_r >= 2) or (prob_delta >= 0.35):
            return "SUDDEN_DETERIORATION"

        # Deteriorating: jump >= 1 level, or probability increase >= +0.10
        if (curr_r > prev_r) or (prob_delta >= 0.10):
            return "DETERIORATING"

        # Recovery detected: was severe/high and now dropped to moderate/low with large prob reduction
        if (prev_r >= 2 and curr_r <= 1) and (prob_delta <= -0.20):
            return "RECOVERY_DETECTED"

        # Improving: risk rank dropped or probability decreased >= -0.10
        if (curr_r < prev_r) or (prob_delta <= -0.10):
            return "IMPROVING"

        return "STABLE"

    def record_prediction_and_detect_delta(
        self,
        db: Session,
        prediction_item: dict[str, Any],
        trigger_type: str = "scheduled",
    ) -> PredictionDelta:
        """Persist prediction history snapshot and compute cycle-over-cycle delta."""
        grid_id = int(prediction_item["grid_id"])
        grid_name = str(prediction_item.get("grid_name", f"Grid {grid_id}"))
        curr_level = str(prediction_item.get("prediction", prediction_item.get("risk_level", "Low")))
        curr_prob = float(prediction_item.get("probability", 0.0))
        confidence = float(prediction_item.get("confidence", 0.85))
        conf_cat = str(prediction_item.get("confidence_category", "High"))
        rain_mm = float(prediction_item.get("rainfall_mm", 0.0))
        rain_3d = float(prediction_item.get("rainfall_3d_mm", 0.0))
        rain_7d = float(prediction_item.get("rainfall_7d_mm", 0.0))
        model_ver = str(prediction_item.get("model_version", "v5.0.0"))
        horizon = str(prediction_item.get("horizon", "nowcast"))
        is_fallback = bool(prediction_item.get("is_fallback", False))
        features = prediction_item.get("features", {})
        contributions = prediction_item.get("contributing_features", [])

        # Fetch immediate previous prediction for this grid and horizon
        prev_record = (
            db.query(PredictionHistory)
            .filter(
                PredictionHistory.grid_id == grid_id,
                PredictionHistory.horizon == horizon,
            )
            .order_by(desc(PredictionHistory.predicted_at))
            .first()
        )

        prev_level = prev_record.risk_level if prev_record else None
        prev_prob = prev_record.probability if prev_record else None
        prev_rain = prev_record.rainfall_mm if prev_record else 0.0
        prev_conf = prev_record.confidence if prev_record else confidence

        prob_delta = (curr_prob - prev_prob) if prev_prob is not None else 0.0
        rain_delta = rain_mm - prev_rain
        conf_delta = confidence - prev_conf

        trend = self.classify_trend(prev_level, curr_level, prev_prob, curr_prob)

        now_dt = datetime.utcnow()

        # 1. Insert into prediction_history
        new_hist = PredictionHistory(
            grid_id=grid_id,
            horizon=horizon,
            predicted_at=now_dt,
            risk_level=curr_level,
            probability=curr_prob,
            confidence=confidence,
            confidence_category=conf_cat,
            rainfall_mm=rain_mm,
            rainfall_3d_mm=rain_3d,
            rainfall_7d_mm=rain_7d,
            model_version=model_ver,
            trigger_type=trigger_type,
            is_fallback=is_fallback,
            features_json=json.dumps(features),
            contributing_features_json=json.dumps(contributions),
        )
        db.add(new_hist)

        # 2. Record transition in risk_transitions if trend shifted or significant probability movement
        if trend != "STABLE" or abs(prob_delta) >= 0.05:
            trans_rec = RiskTransitionRecord(
                grid_id=grid_id,
                previous_risk=prev_level,
                current_risk=curr_level,
                previous_probability=prev_prob,
                current_probability=curr_prob,
                probability_delta=round(prob_delta, 4),
                trend=trend,
                horizon=horizon,
                detected_at=now_dt,
            )
            db.add(trans_rec)

        return PredictionDelta(
            grid_id=grid_id,
            grid_name=grid_name,
            previous_probability=prev_prob,
            current_probability=curr_prob,
            probability_delta=prob_delta,
            previous_level=prev_level,
            current_level=curr_level,
            trend=trend,
            rainfall_delta=rain_delta,
            confidence_delta=conf_delta,
            horizon=horizon,
        )

    def get_grid_risk_trends(
        self,
        db: Session,
        grid_id: int,
        hours: int = 24,
        horizon: str = "nowcast",
    ) -> dict[str, Any]:
        """Retrieve historical risk evolution and trend telemetry for a given sector."""
        grid = db.query(Grid).filter(Grid.id == grid_id).first()
        if not grid:
            raise ValueError(f"Grid sector {grid_id} not found.")

        since_dt = datetime.utcnow() - timedelta(hours=max(1, hours))

        records = (
            db.query(PredictionHistory)
            .filter(
                PredictionHistory.grid_id == grid_id,
                PredictionHistory.horizon == horizon,
                PredictionHistory.predicted_at >= since_dt,
            )
            .order_by(PredictionHistory.predicted_at.asc())
            .all()
        )

        history_items = [r.to_dict() for r in records]

        # Determine current trend
        latest = history_items[-1] if history_items else None
        earliest = history_items[0] if history_items else None

        if latest and earliest and len(history_items) > 1:
            overall_trend = self.classify_trend(
                earliest["risk_level"],
                latest["risk_level"],
                earliest["probability"],
                latest["probability"],
            )
            overall_prob_delta = round(latest["probability"] - earliest["probability"], 4)
        else:
            overall_trend = "STABLE"
            overall_prob_delta = 0.0

        return {
            "grid_id": grid.id,
            "grid_name": grid.name,
            "horizon": horizon,
            "query_window_hours": hours,
            "data_points_count": len(history_items),
            "current_risk_level": latest["risk_level"] if latest else grid.flood_risk,
            "current_probability": latest["probability"] if latest else grid.flood_risk_score,
            "current_confidence": latest["confidence"] if latest else 0.85,
            "overall_trend": overall_trend,
            "overall_probability_delta": overall_prob_delta,
            "history": history_items,
        }


_singleton_risk_trend_service: RiskTrendService | None = None


def get_risk_trend_service() -> RiskTrendService:
    """Retrieve singleton instance of RiskTrendService."""
    global _singleton_risk_trend_service
    if _singleton_risk_trend_service is None:
        _singleton_risk_trend_service = RiskTrendService()
    return _singleton_risk_trend_service
