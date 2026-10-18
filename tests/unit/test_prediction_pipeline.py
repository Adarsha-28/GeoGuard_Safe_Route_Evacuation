"""Unit tests for PredictionPipelineService in GeoGuard V4."""

from unittest.mock import MagicMock, patch
import pytest

from backend.database.connection import SessionLocal
from backend.models.grid import Grid
from backend.models.risk import RiskPrediction
from backend.services.prediction_pipeline_service import (
    PredictionPipelineService,
    get_prediction_pipeline_service,
)
from backend.services.weather_ingestion_service import WeatherIngestionResult


@pytest.fixture
def pipeline_service():
    return get_prediction_pipeline_service()


@pytest.fixture
def mock_weather():
    return WeatherIngestionResult(
        success=True,
        rainfall_current_mm=35.0,
        wind_speed_kmh=12.0,
        daily_rainfall_history=[10.0, 15.0, 25.0, 0.0, 10.0, 20.0, 35.0],
    )


def test_batch_ml_prediction_success(pipeline_service, mock_weather):
    """Verify batch prediction run across monitored grids with valid audit trail."""
    with SessionLocal() as db:
        result = pipeline_service.run_prediction_pipeline(
            db=db,
            weather_result=mock_weather,
            trigger_type="test_run",
        )

    assert result.total_grids > 0
    assert len(result.predictions) == result.total_grids
    assert result.execution_time_ms > 0.0

    # Verify predictions have valid probabilities and levels
    for p in result.predictions:
        assert p.risk_level in ("Low", "Moderate", "High", "Severe")
        assert 0.0 <= p.probability <= 1.0
        assert p.model_version != ""

    # Verify audit trail record exists in database
    with SessionLocal() as db:
        audit_records = (
            db.query(RiskPrediction)
            .filter(RiskPrediction.trigger_type == "test_run")
            .all()
        )
        assert len(audit_records) == result.total_grids
        # Clean up test audit records
        db.query(RiskPrediction).filter(RiskPrediction.trigger_type == "test_run").delete()
        db.commit()


def test_prediction_fallback_when_model_disabled(pipeline_service, mock_weather):
    """Verify automatic deterministic fallback when ML is disabled via settings."""
    with patch("backend.services.ml_prediction_service.MLPredictionService.is_available", False):
        with SessionLocal() as db:
            result = pipeline_service.run_prediction_pipeline(
                db=db,
                weather_result=mock_weather,
                trigger_type="test_fallback",
            )

    assert result.fallback_active is True
    for p in result.predictions:
        assert p.is_fallback is True
        assert "fallback" in (p.model_version or "").lower()

    # Clean up test records
    with SessionLocal() as db:
        db.query(RiskPrediction).filter(RiskPrediction.trigger_type == "test_fallback").delete()
        db.commit()


def test_prediction_resilience_on_feature_error(pipeline_service, mock_weather):
    """Verify that feature generation or model inference errors do not crash batch prediction."""
    with patch.object(
        pipeline_service.ml_service, "predict_sector_risk", side_effect=RuntimeError("Simulated inference error")
    ):
        with SessionLocal() as db:
            result = pipeline_service.run_prediction_pipeline(
                db=db,
                weather_result=mock_weather,
                trigger_type="test_resilience",
            )

    assert result.fallback_active is True
    assert result.total_grids > 0
    for p in result.predictions:
        assert p.is_fallback is True

    # Clean up test records
    with SessionLocal() as db:
        db.query(RiskPrediction).filter(RiskPrediction.trigger_type == "test_resilience").delete()
        db.commit()
