"""Machine Learning Flood Risk Prediction Service for GeoGuard V3.

Loads the trained scikit-learn pipeline and metadata once at startup.
Provides inference, probability estimation, feature attribution, and
graceful fallback to the V2 deterministic formula when ML is unavailable.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from backend.config import ROOT_DIR, logger, settings
from backend.services.risk_service import calculate_flood_risk_score, classify_risk_level

MODEL_PATH = ROOT_DIR / "models" / "trained" / "geoguard_flood_rf_v3.joblib"
METADATA_PATH = ROOT_DIR / "models" / "metadata" / "model_metadata_v3.json"

EXPECTED_V3_FEATURES = [
    "rainfall_current_mm",
    "rainfall_3d_accum_mm",
    "rainfall_7d_accum_mm",
    "elevation_m",
    "distance_to_water_m",
    "latitude",
    "longitude",
    "month",
]


class MLPredictionService:
    """Singleton service for empirical ML flood risk forecasting."""

    def __init__(self, model_path: Path | None = None, metadata_path: Path | None = None) -> None:
        self.model_path = model_path or MODEL_PATH
        self.metadata_path = metadata_path or METADATA_PATH
        self._lock = threading.Lock()
        self._pipeline: Any = None
        self._metadata: dict[str, Any] = {}
        self._is_loaded: bool = False
        self._fallback_reason: str | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load trained pipeline and metadata artifacts into memory with strict safety validation."""
        with self._lock:
            # 1. Check if ML is enabled by configuration
            if not getattr(settings, "ML_ENABLED", True):
                self._fallback_reason = "ML_ENABLED is set to False in system configuration."
                logger.warning(f"Model safety check: {self._fallback_reason} Entering deterministic fallback mode.")
                self._is_loaded = False
                return

            # 2. Check model artifact existence
            if not self.model_path.exists():
                self._fallback_reason = f"ML model artifact not found at {self.model_path}."
                logger.warning(
                    f"Model safety check: {self._fallback_reason} "
                    f"Inference service will operate in deterministic fallback mode."
                )
                self._is_loaded = False
                return

            try:
                # 3. Load model artifact
                self._pipeline = joblib.load(self.model_path)

                # 4. Load and validate metadata
                if not self.metadata_path.exists():
                    self._fallback_reason = f"Metadata artifact not found at {self.metadata_path}."
                    logger.warning(f"Model safety check failed: {self._fallback_reason} Entering fallback.")
                    self._is_loaded = False
                    return

                with open(self.metadata_path, mode="r", encoding="utf-8") as f:
                    self._metadata = json.load(f)

                # 5. Verify expected feature names and order
                meta_features = self._metadata.get("features", [])
                if meta_features != EXPECTED_V3_FEATURES:
                    self._fallback_reason = (
                        f"Feature schema mismatch. Expected {EXPECTED_V3_FEATURES}, found {meta_features}."
                    )
                    logger.error(f"Model safety check failed: {self._fallback_reason} Entering fallback mode.")
                    self._is_loaded = False
                    return

                # 6. Verify feature count
                if len(meta_features) != 8:
                    self._fallback_reason = f"Expected exactly 8 features, found {len(meta_features)}."
                    logger.error(f"Model safety check failed: {self._fallback_reason} Entering fallback mode.")
                    self._is_loaded = False
                    return

                # 7. Verify model version
                active_expected_version = getattr(settings, "ACTIVE_MODEL_VERSION", "v3.0.0")
                meta_version = str(self._metadata.get("model_version", ""))
                if meta_version != active_expected_version:
                    self._fallback_reason = (
                        f"Model version mismatch: expected '{active_expected_version}', got '{meta_version}'."
                    )
                    logger.error(f"Model safety check failed: {self._fallback_reason} Entering fallback mode.")
                    self._is_loaded = False
                    return

                self._is_loaded = True
                self._fallback_reason = None
                logger.info(
                    f"GeoGuard ML model verified and loaded successfully: {self._metadata.get('algorithm', 'ML')} "
                    f"({self._metadata.get('model_version', 'v3.0.0')})"
                )
            except Exception as e:
                self._fallback_reason = f"Failed to load ML model artifact: {e}"
                logger.error(f"Model safety check error: {self._fallback_reason}")
                self._is_loaded = False

    @property
    def is_available(self) -> bool:
        """Check if trained ML model is ready for inference."""
        return self._is_loaded and self._pipeline is not None

    @property
    def model_version(self) -> str:
        """Retrieve active model version string."""
        if self.is_available:
            return str(self._metadata.get("model_version", "v3.0.0"))
        return "v2.0-deterministic-fallback"

    @property
    def fallback_reason(self) -> str | None:
        """Return the reason ML is operating in fallback mode, if any."""
        return self._fallback_reason

    def predict_sector_risk(
        self,
        rainfall_current_mm: float,
        rainfall_3d_accum_mm: float,
        rainfall_7d_accum_mm: float,
        elevation_m: float,
        distance_to_water_m: float,
        latitude: float,
        longitude: float,
        month: int | None = None,
    ) -> dict[str, Any]:
        """Perform empirical ML risk inference with feature validation and fallback safety."""
        month_val = month or datetime.utcnow().month

        # Fallback to V2 deterministic model if ML artifact is unready
        if not self.is_available:
            return self._deterministic_fallback(
                rainfall_current_mm, elevation_m, distance_to_water_m
            )

        try:
            import pandas as pd
            features_df = pd.DataFrame(
                [[
                    float(rainfall_current_mm),
                    float(rainfall_3d_accum_mm),
                    float(rainfall_7d_accum_mm),
                    float(elevation_m),
                    float(distance_to_water_m),
                    float(latitude),
                    float(longitude),
                    int(month_val),
                ]],
                columns=[
                    "rainfall_current_mm",
                    "rainfall_3d_accum_mm",
                    "rainfall_7d_accum_mm",
                    "elevation_m",
                    "distance_to_water_m",
                    "latitude",
                    "longitude",
                    "month",
                ],
            )

            pred_class = int(self._pipeline.predict(features_df)[0])
            probabilities = self._pipeline.predict_proba(features_df)[0]
            prob_flood = float(probabilities[1]) if len(probabilities) > 1 else float(pred_class)

            # Map probability and class to operational risk level
            if prob_flood < 0.25:
                risk_level = "Low"
            elif prob_flood < 0.60:
                risk_level = "Moderate"
            elif prob_flood < 0.85:
                risk_level = "High"
            else:
                risk_level = "Severe"

            # Top contributing feature attributions based on domain rules and importance
            contributions = [
                {"feature": "3-Day Accumulated Rainfall", "value": f"{rainfall_3d_accum_mm:.1f} mm", "impact": "High" if rainfall_3d_accum_mm > 50 else "Moderate"},
                {"feature": "7-Day Cumulative Rainfall", "value": f"{rainfall_7d_accum_mm:.1f} mm", "impact": "High" if rainfall_7d_accum_mm > 100 else "Moderate"},
                {"feature": "Terrain Elevation", "value": f"{elevation_m:.1f} m", "impact": "High Hazard" if elevation_m <= 3.0 else "Low Hazard"},
                {"feature": "Proximity to Water Basin", "value": f"{distance_to_water_m:.0f} m", "impact": "High Hazard" if distance_to_water_m <= 400 else "Low Hazard"},
            ]

            return {
                "prediction": risk_level,
                "probability": round(prob_flood, 4),
                "model_version": self.model_version,
                "algorithm": self._metadata.get("algorithm", "Gradient Boosting"),
                "prediction_horizon": "24-Hour Flood Inundation Hazard",
                "is_fallback": False,
                "contributing_features": contributions,
            }

        except Exception as e:
            logger.warning(f"ML inference error: {e}. Executing deterministic fallback.")
            return self._deterministic_fallback(
                rainfall_current_mm, elevation_m, distance_to_water_m
            )

    def _deterministic_fallback(
        self, rainfall_mm: float, elevation_m: float, distance_to_water_m: float
    ) -> dict[str, Any]:
        """Transparent fallback returning V2 deterministic calculation."""
        rain_score = min(1.0, float(rainfall_mm) / 150.0)
        # Bounded between 1m - 20m elevation and 100m - 5000m water distance
        elev_score = max(0.0, min(1.0, (16.0 - float(elevation_m)) / 15.0))
        water_score = max(0.0, min(1.0, (5000.0 - float(distance_to_water_m)) / 4900.0))

        score = calculate_flood_risk_score(rain_score, elev_score, water_score)
        level = classify_risk_level(score)

        return {
            "prediction": level,
            "probability": round(score, 4),
            "model_version": "v2.0-deterministic-fallback",
            "algorithm": "Deterministic Multi-Criteria Formula",
            "prediction_horizon": "24-Hour Flood Inundation Hazard",
            "is_fallback": True,
            "contributing_features": [
                {"feature": "Rainfall Component (50%)", "value": f"{rainfall_mm:.1f} mm", "impact": "Direct Weight"},
                {"feature": "Elevation Component (25%)", "value": f"{elevation_m:.1f} m", "impact": "Inverted Weight"},
                {"feature": "Water Proximity Component (25%)", "value": f"{distance_to_water_m:.0f} m", "impact": "Inverted Weight"},
            ],
        }


_singleton_ml_service: MLPredictionService | None = None


def get_ml_prediction_service() -> MLPredictionService:
    """Retrieve singleton instance of MLPredictionService."""
    global _singleton_ml_service
    if _singleton_ml_service is None:
        _singleton_ml_service = MLPredictionService()
    return _singleton_ml_service
