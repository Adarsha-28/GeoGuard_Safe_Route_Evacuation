"""Unit tests for FeatureService in GeoGuard V4."""

from datetime import datetime
import pytest

from backend.models.grid import Grid
from backend.services.feature_service import (
    BOUNDS,
    V3_FEATURE_NAMES,
    FeatureService,
    get_feature_service,
)


@pytest.fixture
def feature_service():
    return get_feature_service()


@pytest.fixture
def sample_grid():
    return Grid(
        id=1,
        name="Adyar",
        latitude=13.0012,
        longitude=80.2565,
        elevation_m=4.2,
        distance_to_water=180.0,
        rainfall_mm=25.0,
        flood_risk_score=0.45,
        flood_risk="Moderate",
    )


def test_feature_order_and_schema(feature_service, sample_grid):
    """Verify strictly ordered 8 features matching V3 training requirements."""
    res = feature_service.generate_sector_features(
        grid=sample_grid,
        rainfall_current_mm=25.0,
        rainfall_3d_accum_mm=60.0,
        rainfall_7d_accum_mm=110.0,
        observation_dt=datetime(2026, 9, 3, 10, 0),
        is_data_sufficient=True,
    )

    assert res.is_valid is True
    assert res.is_data_sufficient is True
    assert res.data_availability_state == "full"
    assert len(res.ordered_feature_values) == 8

    # Verify exact feature order
    expected_values = [
        25.0,     # rainfall_current_mm
        60.0,     # rainfall_3d_accum_mm
        110.0,    # rainfall_7d_accum_mm
        4.2,      # elevation_m
        180.0,    # distance_to_water_m
        13.0012,  # latitude
        80.2565,  # longitude
        9,        # month (September)
    ]
    assert res.ordered_feature_values == expected_values


def test_rolling_accumulations_calculation(feature_service):
    """Verify 3-day and 7-day antecedent precipitation sum calculations."""
    daily_history = [5.0, 10.0, 15.0, 20.0, 0.0, 30.0, 25.0]
    p_3d, p_7d, sufficient = feature_service.calculate_rolling_accumulations_from_history(
        daily_history=daily_history, current_rain=25.0
    )

    # Last 3 days: [0.0, 30.0, 25.0] -> 55.0
    assert p_3d == 55.0
    # Last 7 days: sum of all 7 -> 105.0
    assert p_7d == 105.0
    assert sufficient is True


def test_insufficient_history_handling(feature_service, sample_grid):
    """Verify that when history is insufficient, fallback state is triggered instead of fake data."""
    short_history = [10.0]  # Only 1 day available
    p_3d, p_7d, sufficient = feature_service.calculate_rolling_accumulations_from_history(
        daily_history=short_history, current_rain=10.0
    )
    assert sufficient is False

    res = feature_service.generate_sector_features(
        grid=sample_grid,
        rainfall_current_mm=10.0,
        rainfall_3d_accum_mm=p_3d,
        rainfall_7d_accum_mm=p_7d,
        is_data_sufficient=sufficient,
    )
    assert res.is_data_sufficient is False
    assert res.data_availability_state == "insufficient_history"


def test_feature_bounds_validation(feature_service):
    """Verify that impossible physical values fail validation."""
    valid_features = {
        "rainfall_current_mm": 20.0,
        "rainfall_3d_accum_mm": 50.0,
        "rainfall_7d_accum_mm": 100.0,
        "elevation_m": 5.0,
        "distance_to_water_m": 250.0,
        "latitude": 13.0827,
        "longitude": 80.2707,
        "month": 9,
    }
    is_ok, err = feature_service.validate_features(valid_features)
    assert is_ok is True
    assert err is None

    # Test out of bounds elevation
    bad_features = dict(valid_features, elevation_m=999.0)
    is_ok, err = feature_service.validate_features(bad_features)
    assert is_ok is False
    assert "elevation_m" in err

    # Test out of bounds month
    bad_month = dict(valid_features, month=13)
    is_ok, err = feature_service.validate_features(bad_month)
    assert is_ok is False
    assert "month" in err


def test_feature_missing_or_null(feature_service):
    """Verify that missing or None features trigger validation errors."""
    incomplete_features = {
        "rainfall_current_mm": 20.0,
        # missing 3d, 7d etc.
    }
    is_ok, err = feature_service.validate_features(incomplete_features)
    assert is_ok is False
    assert "Missing required feature" in err

    null_feature = {
        "rainfall_current_mm": None,
        "rainfall_3d_accum_mm": 50.0,
        "rainfall_7d_accum_mm": 100.0,
        "elevation_m": 5.0,
        "distance_to_water_m": 250.0,
        "latitude": 13.0827,
        "longitude": 80.2707,
        "month": 9,
    }
    is_ok, err = feature_service.validate_features(null_feature)
    assert is_ok is False
    assert "None" in err
