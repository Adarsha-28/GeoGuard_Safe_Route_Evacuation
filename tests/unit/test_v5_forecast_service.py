"""Unit tests for GeoGuard V5 ForecastService and Prediction Horizon Engine."""

import pytest
from unittest.mock import MagicMock, patch
from backend.services.forecast_service import ForecastService, HorizonForecastData, VALID_HORIZONS


def test_horizon_forecast_data_accumulation():
    """Verify HorizonForecastData stores and retrieves accumulations correctly."""
    data = HorizonForecastData(
        nowcast_mm=5.5,
        h6_mm=22.0,
        h12_mm=45.0,
        h24_mm=88.5,
        daily_history=[10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0],
    )
    assert data.get_rainfall_for_horizon("nowcast") == 5.5
    assert data.get_rainfall_for_horizon("current") == 5.5
    assert data.get_rainfall_for_horizon("6h") == 22.0
    assert data.get_rainfall_for_horizon("12h") == 45.0
    assert data.get_rainfall_for_horizon("24h") == 88.5

    with pytest.raises(ValueError, match="Invalid forecast horizon"):
        data.get_rainfall_for_horizon("48h")


def test_valid_horizons_set():
    """Ensure exact operational horizons are defined."""
    assert "nowcast" in VALID_HORIZONS
    assert "6h" in VALID_HORIZONS
    assert "12h" in VALID_HORIZONS
    assert "24h" in VALID_HORIZONS


def test_forecast_service_predict_for_horizon_validation():
    """Verify validation error on unrecognized horizon."""
    service = ForecastService()
    mock_db = MagicMock()
    with pytest.raises(ValueError, match="Invalid horizon"):
        service.predict_for_horizon(mock_db, horizon="invalid_horizon")


def test_forecast_service_predict_fields_and_bounds():
    """Verify prediction output structure, confidence, and feature attributions."""
    service = ForecastService()
    mock_db = MagicMock()

    mock_grid = MagicMock()
    mock_grid.id = 1
    mock_grid.name = "Velachery"
    mock_grid.elevation_m = 4.2
    mock_grid.distance_to_water = 250.0
    mock_grid.latitude = 12.9815
    mock_grid.longitude = 80.2180

    mock_db.query.return_value.filter.return_value.all.return_value = [mock_grid]
    mock_db.query.return_value.order_by.return_value.all.return_value = [mock_grid]

    dummy_forecast = HorizonForecastData(
        nowcast_mm=12.0,
        h6_mm=35.0,
        h12_mm=60.0,
        h24_mm=110.0,
        daily_history=[5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    )

    results = service.predict_for_horizon(mock_db, horizon="6h", forecast_data=dummy_forecast)

    assert len(results) == 1
    res = results[0]
    assert res["grid_id"] == 1
    assert res["grid_name"] == "Velachery"
    assert res["horizon"] == "6h"
    assert res["rainfall_mm"] == 35.0
    assert 0.0 <= res["probability"] <= 1.0
    assert res["risk_level"] in ("Low", "Moderate", "High", "Severe")
    assert 0.0 <= res["confidence"] <= 1.0
    assert res["confidence_category"] in ("High confidence", "Medium confidence", "Low confidence")
    assert len(res["contributing_features"]) == 8
