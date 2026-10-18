"""Unit tests for MLPredictionService inference, feature validation, and fallback logic."""

from pathlib import Path
import pytest

from backend.services.ml_prediction_service import MLPredictionService, get_ml_prediction_service


def test_ml_service_singleton_and_loading():
    """Verify MLPredictionService initializes and loads trained artifact."""
    service = get_ml_prediction_service()
    assert service.is_available is True
    assert service.model_version == "v3.0.0"


def test_ml_prediction_bounds_and_determinism():
    """Verify probability outputs fall strictly in [0.0, 1.0] and predictions are reproducible."""
    service = get_ml_prediction_service()

    # Extreme storm conditions (85mm current, 130mm 3d, low elevation, near river)
    pred_storm = service.predict_sector_risk(
        rainfall_current_mm=85.0,
        rainfall_3d_accum_mm=130.0,
        rainfall_7d_accum_mm=220.0,
        elevation_m=2.0,
        distance_to_water_m=200.0,
        latitude=13.0418,
        longitude=80.2341,
        month=11,
    )

    assert 0.0 <= pred_storm["probability"] <= 1.0
    assert pred_storm["prediction"] in ("Low", "Moderate", "High", "Severe")
    assert pred_storm["is_fallback"] is False
    assert len(pred_storm["contributing_features"]) > 0

    # Repeat inference with identical inputs must be deterministic
    pred_repeat = service.predict_sector_risk(
        rainfall_current_mm=85.0,
        rainfall_3d_accum_mm=130.0,
        rainfall_7d_accum_mm=220.0,
        elevation_m=2.0,
        distance_to_water_m=200.0,
        latitude=13.0418,
        longitude=80.2341,
        month=11,
    )
    assert pred_storm["probability"] == pred_repeat["probability"]
    assert pred_storm["prediction"] == pred_repeat["prediction"]


def test_ml_service_graceful_fallback():
    """Verify service automatically falls back to deterministic formula when model is missing."""
    # Instantiate with non-existent path
    dummy_service = MLPredictionService(model_path=Path("non_existent_model.joblib"))
    assert dummy_service.is_available is False
    assert "fallback" in dummy_service.model_version

    fallback_res = dummy_service.predict_sector_risk(
        rainfall_current_mm=50.0,
        rainfall_3d_accum_mm=75.0,
        rainfall_7d_accum_mm=100.0,
        elevation_m=5.0,
        distance_to_water_m=1000.0,
        latitude=13.0418,
        longitude=80.2341,
    )

    assert fallback_res["is_fallback"] is True
    assert fallback_res["model_version"] == "v2.0-deterministic-fallback"
    assert 0.0 <= fallback_res["probability"] <= 1.0
    assert fallback_res["prediction"] in ("Low", "Moderate", "High", "Severe")
