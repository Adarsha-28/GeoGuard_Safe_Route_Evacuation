"""Unit tests for WeatherIngestionService in GeoGuard V4."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch
import urllib.error

import pytest
from sqlalchemy.orm import Session

from backend.database.connection import SessionLocal
from backend.models.weather import WeatherObservation
from backend.services.weather_ingestion_service import (
    WeatherIngestionResult,
    WeatherIngestionService,
)


@pytest.fixture
def weather_service():
    return WeatherIngestionService(max_retries=1, timeout=2.0)


def test_weather_ingestion_success(weather_service):
    """Verify parsing and storing valid live weather payload from Open-Meteo."""
    payload = {
        "latitude": 13.0827,
        "longitude": 80.2707,
        "current": {
            "time": "2026-09-03T11:00",
            "precipitation": 42.5,
            "rain": 42.5,
            "wind_speed_10m": 15.2,
        },
        "daily": {
            "time": ["2026-09-01", "2026-09-02", "2026-09-03"],
            "precipitation_sum": [10.0, 20.0, 42.5],
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__.return_value = mock_resp

    with SessionLocal() as db:
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = weather_service.ingest_current_weather(db)

    assert result.success is True
    assert result.rainfall_current_mm == 42.5
    assert result.wind_speed_kmh == 15.2
    assert len(result.daily_rainfall_history) == 3
    assert weather_service.last_sync_status == "healthy"


def test_weather_ingestion_timeout(weather_service):
    """Verify graceful handling when Open-Meteo times out."""
    with SessionLocal() as db:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            result = weather_service.ingest_current_weather(db)

    assert result.success is False
    assert "timed out" in (result.error_message or "").lower()
    assert weather_service.last_sync_status in ("degraded", "unavailable")


def test_weather_ingestion_http_error(weather_service):
    """Verify non-200 HTTP response handling."""
    http_err = urllib.error.HTTPError(
        "https://api.open-meteo.com", 503, "Service Unavailable", {}, None
    )
    with SessionLocal() as db:
        with patch("urllib.request.urlopen", side_effect=http_err):
            result = weather_service.ingest_current_weather(db)

    assert result.success is False
    assert "503" in (result.error_message or "")


def test_weather_ingestion_malformed_json(weather_service):
    """Verify handling of invalid/corrupt JSON response."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b"{not-valid-json: ["
    mock_resp.__enter__.return_value = mock_resp

    with SessionLocal() as db:
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = weather_service.ingest_current_weather(db)

    assert result.success is False
    assert "malformed json" in (result.error_message or "").lower()


def test_weather_ingestion_invalid_bounds(weather_service):
    """Verify rejection of physically impossible weather parameters (e.g. negative or extreme rainfall)."""
    bad_payload = {
        "current": {
            "time": "2026-09-03T11:00",
            "precipitation": -99.0,  # Impossible negative precipitation
            "rain": -99.0,
        }
    }
    is_valid, err = weather_service.validate_weather_payload(bad_payload)
    assert is_valid is False
    assert "physical bounds" in (err or "").lower()

    bad_wind = {
        "current": {
            "time": "2026-09-03T11:00",
            "precipitation": 10.0,
            "wind_speed_10m": 9999.0,  # Impossible wind speed
        }
    }
    is_valid, err = weather_service.validate_weather_payload(bad_wind)
    assert is_valid is False
    assert "bounds" in (err or "").lower()


def test_weather_ingestion_duplicate_suppression(weather_service):
    """Verify deduplication strategy prevents redundant identical observations."""
    obs_time = datetime(2026, 9, 3, 14, 0, 0)
    payload = {
        "latitude": 13.0827,
        "longitude": 80.2707,
        "current": {
            "time": obs_time.strftime("%Y-%m-%dT%H:%M"),
            "precipitation": 25.0,
            "rain": 25.0,
            "wind_speed_10m": 10.0,
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__.return_value = mock_resp

    with SessionLocal() as db:
        with patch("urllib.request.urlopen", return_value=mock_resp):
            # First ingestion
            res1 = weather_service.ingest_current_weather(db)
            assert res1.success is True

            # Immediate second ingestion of identical timestamp & coords
            res2 = weather_service.ingest_current_weather(db)
            assert res2.success is True
            assert res2.is_duplicate is True
