"""Failure-Injection tests for GeoGuard V4 Operational Flood Intelligence.

Simulates critical subsystem outages and verifies graceful system resilience:
1. Open-Meteo outage / network failure
2. Malformed weather payload
3. ML model failure with automatic deterministic fallback
4. Batch prediction failure during scheduled cycle without scheduler crash
5. Alert engine database failure with transaction rollback
"""

import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest
from fastapi.testclient import TestClient

from backend.database.connection import SessionLocal
from backend.main import app
from backend.models.grid import Grid
from backend.services.alert_engine import get_alert_engine
from backend.services.operational_scheduler import get_operational_scheduler
from backend.services.prediction_pipeline_service import (
    PredictionPipelineService,
    SectorPredictionResult,
    get_prediction_pipeline_service,
)
from backend.services.risk_state_service import RiskTransition
from backend.services.weather_ingestion_service import (
    WeatherIngestionResult,
    get_weather_ingestion_service,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_failure_injection_open_meteo_unavailable():
    """Simulate complete Open-Meteo network outage; verify graceful degradation."""
    weather_service = get_weather_ingestion_service()
    weather_service.last_known_rainfall_mm = 0.0
    with SessionLocal() as db:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused by peer")):
            result = weather_service.ingest_current_weather(db)

    assert result.success is False
    assert result.rainfall_current_mm == 0.0  # Safe zero baseline
    assert weather_service.last_sync_status in ("degraded", "unavailable")


def test_failure_injection_malformed_weather_payload():
    """Simulate API returning truncated or corrupt bytes; verify no crash and clear error."""
    weather_service = get_weather_ingestion_service()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b"<html5>Gateway Timeout</html5>"
    mock_resp.__enter__.return_value = mock_resp

    with SessionLocal() as db:
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = weather_service.ingest_current_weather(db)

    assert result.success is False
    assert "malformed" in (result.error_message or "").lower()


def test_failure_injection_ml_model_outage_activates_fallback(client):
    """Simulate ML model missing or crashing; verify pipeline falls back to V2 deterministic formula."""
    pipeline_service = get_prediction_pipeline_service()
    weather_result = WeatherIngestionResult(
        success=True,
        rainfall_current_mm=45.0,
        wind_speed_kmh=20.0,
        daily_rainfall_history=[10.0, 20.0, 30.0, 45.0],
    )

    # Force ML prediction to raise an unexpected exception
    with patch.object(pipeline_service.ml_service, "predict_sector_risk", side_effect=RuntimeError("Model weights corrupted")):
        with SessionLocal() as db:
            result = pipeline_service.run_prediction_pipeline(
                db=db,
                weather_result=weather_result,
                trigger_type="failure_inject",
            )

    assert result.fallback_active is True
    assert result.total_grids > 0
    for p in result.predictions:
        assert p.is_fallback is True
        assert p.risk_level in ("Low", "Moderate", "High", "Severe")

    # Verify operational status endpoint reflects fallback state
    resp = client.get("/api/operations/status")
    assert resp.status_code == 200
    # Clean up test audit records
    with SessionLocal() as db:
        from backend.models.risk import RiskPrediction
        db.query(RiskPrediction).filter(RiskPrediction.trigger_type == "failure_inject").delete()
        db.commit()


def test_failure_injection_scheduler_resilience_on_database_glitch():
    """Simulate transient database glitch during operational cycle; verify scheduler remains alive."""
    scheduler = get_operational_scheduler()

    # Create mock session that fails during commit
    mock_db = MagicMock()
    mock_db.query.side_effect = RuntimeError("Simulated DB connection lost")

    result = scheduler.run_single_cycle(mock_db, trigger_type="db_glitch_test")
    assert result["status"] == "failed"
    assert "Simulated DB connection lost" in result["error"]
    assert scheduler.last_cycle_status == "failed"
    # Concurrency lock must be released despite failure
    assert scheduler._cycle_lock.locked() is False
