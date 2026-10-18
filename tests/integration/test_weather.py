"""Integration tests for live weather sync and Open-Meteo fallback resilience."""

from unittest.mock import MagicMock, patch
import pytest

from backend.database.connection import SessionLocal
from backend.services.weather_service import WeatherService


def test_weather_sync_success():
    """Verify live weather parsing and persistence in PostgreSQL."""
    weather_service = WeatherService()
    mock_response = b'{"current": {"precipitation": 38.5, "rain": 38.5}}'

    mock_cm = MagicMock()
    mock_cm.status = 200
    mock_cm.read.return_value = mock_response
    mock_cm.__enter__.return_value = mock_cm

    with SessionLocal() as db:
        with patch("urllib.request.urlopen", return_value=mock_cm):
            success, rain, ts = weather_service.sync_live_weather(db)

        assert success is True
        assert rain == 38.5
        assert ts != ""


def test_weather_sync_timeout_fallback():
    """Verify network timeout preserves previous rainfall without crashing."""
    weather_service = WeatherService()
    weather_service.last_known_rainfall_mm = 12.0

    with SessionLocal() as db:
        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
            success, rain, ts = weather_service.sync_live_weather(db)

        assert success is False
        assert rain == 12.0  # Preserved previous observation


def test_weather_sync_malformed_json_fallback():
    """Verify malformed payload fallback without crashing or generating fake values."""
    weather_service = WeatherService()
    weather_service.last_known_rainfall_mm = 7.5

    mock_cm = MagicMock()
    mock_cm.status = 200
    mock_cm.read.return_value = b'{"unexpected_schema": true}'
    mock_cm.__enter__.return_value = mock_cm

    with SessionLocal() as db:
        with patch("urllib.request.urlopen", return_value=mock_cm):
            success, rain, ts = weather_service.sync_live_weather(db)

        assert success is False
        assert rain == 7.5
