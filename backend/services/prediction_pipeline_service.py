"""Automatic V3 Prediction Pipeline Service for GeoGuard V4.

Executes continuous batch inference for all monitored grids:
1. Retrieves active monitored grids from PostGIS
2. Retrieves latest weather observations & rolling accumulations
3. Generates validated V3 feature vectors
4. Executes V3 Gradient Boosting ML model
5. Persists historical predictions with audit metadata (trigger_type='scheduled'|'manual')
6. Gracefully handles fallbacks to V2 deterministic model if ML is unready or data is insufficient
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.config import logger
from backend.models.grid import Grid
from backend.models.risk import RiskPrediction
from backend.services.feature_service import FeatureService, get_feature_service
from backend.services.ml_prediction_service import MLPredictionService, get_ml_prediction_service
from backend.services.weather_ingestion_service import WeatherIngestionResult


class SectorPredictionResult:
    """Prediction output for an individual grid sector."""

    def __init__(
        self,
        grid_id: int,
        grid_name: str,
        risk_level: str,
        probability: float,
        model_version: str,
        is_fallback: bool,
        fallback_reason: str | None = None,
        features: dict[str, Any] | None = None,
        contributing_features: list[dict[str, Any]] | None = None,
    ) -> None:
        self.grid_id = grid_id
        self.grid_name = grid_name
        self.risk_level = risk_level
        self.probability = round(probability, 4)
        self.model_version = model_version
        self.is_fallback = is_fallback
        self.fallback_reason = fallback_reason
        self.features = features or {}
        self.contributing_features = contributing_features or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_id": self.grid_id,
            "grid_name": self.grid_name,
            "risk_level": self.risk_level,
            "probability": self.probability,
            "model_version": self.model_version,
            "is_fallback": self.is_fallback,
            "fallback_reason": self.fallback_reason,
            "features": self.features,
            "contributing_features": self.contributing_features,
        }


class PredictionPipelineResult:
    """Summary result of a full batch prediction execution cycle."""

    def __init__(
        self,
        predictions: list[SectorPredictionResult],
        total_grids: int,
        fallback_active: bool,
        active_model: str,
        model_version: str,
        calculated_at: datetime,
        execution_time_ms: float,
    ) -> None:
        self.predictions = predictions
        self.total_grids = total_grids
        self.fallback_active = fallback_active
        self.active_model = active_model
        self.model_version = model_version
        self.calculated_at = calculated_at
        self.execution_time_ms = round(execution_time_ms, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_grids": self.total_grids,
            "fallback_active": self.fallback_active,
            "active_model": self.active_model,
            "model_version": self.model_version,
            "calculated_at": self.calculated_at.isoformat(),
            "execution_time_ms": self.execution_time_ms,
            "predictions": [p.to_dict() for p in self.predictions],
        }


class PredictionPipelineService:
    """Orchestrates end-to-end continuous prediction across all monitored sectors."""

    def __init__(
        self,
        feature_service: FeatureService | None = None,
        ml_service: MLPredictionService | None = None,
    ) -> None:
        self.feature_service = feature_service or get_feature_service()
        self.ml_service = ml_service or get_ml_prediction_service()
        self.last_pipeline_run_time: datetime | None = None
        self.last_execution_latency_ms: float = 0.0
        self.last_fallback_state: bool = False

    def run_prediction_pipeline(
        self,
        db: Session,
        weather_result: WeatherIngestionResult | None = None,
        trigger_type: str = "scheduled",
    ) -> PredictionPipelineResult:
        """Run complete prediction cycle for all monitored grids with audit trail persistence."""
        start_time = time.perf_counter()
        logger.info(f"prediction_started: initiating prediction pipeline (trigger={trigger_type})")

        # 1. Fetch all active monitored grids
        grids = db.query(Grid).order_by(Grid.id.asc()).all()
        if not grids:
            logger.warning("No grids found in database for prediction pipeline.")
            return PredictionPipelineResult(
                predictions=[],
                total_grids=0,
                fallback_active=False,
                active_model=self.ml_service.model_version,
                model_version=self.ml_service.model_version,
                calculated_at=datetime.utcnow(),
                execution_time_ms=0.0,
            )

        # 2. Extract precipitation parameters
        curr_rain = weather_result.rainfall_current_mm if weather_result else 0.0
        daily_history = weather_result.daily_rainfall_history if weather_result else []

        # Determine 3d and 7d accumulation
        if daily_history and len(daily_history) >= 3:
            accum_3d, accum_7d, is_data_sufficient = (
                self.feature_service.calculate_rolling_accumulations_from_history(daily_history, curr_rain)
            )
        else:
            accum_3d, accum_7d, is_data_sufficient = (
                self.feature_service.calculate_accumulations_from_db(
                    db, grids[0].latitude, grids[0].longitude, curr_rain
                )
            )

        now_dt = datetime.utcnow()
        prediction_results: list[SectorPredictionResult] = []
        any_fallback = False

        # 3. Process inference and persist snapshots per grid
        for g in grids:
            # Update current measured rainfall on grid
            g.rainfall_mm = curr_rain

            # Feature generation
            feat_result = self.feature_service.generate_sector_features(
                grid=g,
                rainfall_current_mm=curr_rain,
                rainfall_3d_accum_mm=accum_3d,
                rainfall_7d_accum_mm=accum_7d,
                observation_dt=now_dt,
                is_data_sufficient=is_data_sufficient,
            )

            # Check if features are valid and data is sufficient
            if not feat_result.is_valid or not feat_result.is_data_sufficient or not self.ml_service.is_available:
                # Deterministic fallback
                fallback_reason = (
                    feat_result.validation_error
                    if not feat_result.is_valid
                    else "Insufficient weather history for empirical ML prediction"
                    if not feat_result.is_data_sufficient
                    else self.ml_service.fallback_reason or "ML service unavailable"
                )
                pred_dict = self.ml_service._deterministic_fallback(
                    rainfall_mm=curr_rain,
                    elevation_m=g.elevation_m,
                    distance_to_water_m=g.distance_to_water,
                )
                pred_dict["fallback_reason"] = fallback_reason
                any_fallback = True
            else:
                # Empirical ML Prediction
                try:
                    pred_dict = self.ml_service.predict_sector_risk(
                        rainfall_current_mm=curr_rain,
                        rainfall_3d_accum_mm=accum_3d,
                        rainfall_7d_accum_mm=accum_7d,
                        elevation_m=g.elevation_m,
                        distance_to_water_m=g.distance_to_water,
                        latitude=g.latitude,
                        longitude=g.longitude,
                        month=now_dt.month,
                    )
                except Exception as ex:
                    logger.warning(f"Inference exception for grid {g.id}: {ex}. Invoking fallback.")
                    pred_dict = self.ml_service._deterministic_fallback(
                        rainfall_mm=curr_rain,
                        elevation_m=g.elevation_m,
                        distance_to_water_m=g.distance_to_water,
                    )
                    pred_dict["fallback_reason"] = f"Inference exception: {ex}"
                    any_fallback = True

            # Calculate normalized risk score components for auditing
            r_score = min(1.0, curr_rain / 150.0)
            e_score = max(0.0, min(1.0, (16.0 - g.elevation_m) / 15.0))
            w_score = max(0.0, min(1.0, (5000.0 - g.distance_to_water) / 4900.0))
            risk_score = float(pred_dict.get("probability", 0.0))
            risk_level = str(pred_dict.get("prediction", "Low"))

            # Persist historical audit trail in risk_predictions table
            risk_pred_record = RiskPrediction(
                grid_id=g.id,
                risk_score=risk_score,
                risk_level=risk_level,
                rainfall_score=round(r_score, 4),
                elevation_score=round(e_score, 4),
                water_proximity_score=round(w_score, 4),
                model_version=pred_dict.get("model_version", "v3.0.0"),
                probability=pred_dict.get("probability"),
                prediction_horizon=pred_dict.get("prediction_horizon", "24-Hour Hazard"),
                is_fallback=bool(pred_dict.get("is_fallback", False)),
                trigger_type=trigger_type,
                calculated_at=now_dt,
            )
            db.add(risk_pred_record)

            prediction_results.append(
                SectorPredictionResult(
                    grid_id=g.id,
                    grid_name=g.name,
                    risk_level=risk_level,
                    probability=risk_score,
                    model_version=pred_dict.get("model_version", "v3.0.0"),
                    is_fallback=bool(pred_dict.get("is_fallback", False)),
                    fallback_reason=pred_dict.get("fallback_reason"),
                    features=feat_result.features,
                    contributing_features=pred_dict.get("contributing_features", []),
                )
            )

        # Commit batch predictions
        db.commit()

        total_latency = (time.perf_counter() - start_time) * 1000.0
        self.last_pipeline_run_time = now_dt
        self.last_execution_latency_ms = total_latency
        self.last_fallback_state = any_fallback

        if any_fallback:
            logger.warning(
                f"prediction_fallback: prediction completed with fallback active "
                f"for {len(grids)} grids in {total_latency:.2f} ms."
            )
        else:
            logger.info(
                f"prediction_completed: batch ML prediction successful for "
                f"{len(grids)} grids in {total_latency:.2f} ms."
            )

        active_model_name = (
            "Deterministic Fallback Formula"
            if any_fallback
            else self.ml_service._metadata.get("algorithm", "Gradient Boosting")
        )

        return PredictionPipelineResult(
            predictions=prediction_results,
            total_grids=len(grids),
            fallback_active=any_fallback,
            active_model=active_model_name,
            model_version=self.ml_service.model_version,
            calculated_at=now_dt,
            execution_time_ms=total_latency,
        )


_singleton_pipeline_service: PredictionPipelineService | None = None


def get_prediction_pipeline_service() -> PredictionPipelineService:
    """Retrieve singleton instance of PredictionPipelineService."""
    global _singleton_pipeline_service
    if _singleton_pipeline_service is None:
        _singleton_pipeline_service = PredictionPipelineService()
    return _singleton_pipeline_service
