"""Unit tests for deterministic flood risk mathematical formulas and RiskService."""

import pytest
from backend.services.risk_service import (
    calculate_flood_risk_score,
    classify_risk_level,
)


def test_calculate_flood_risk_score_boundaries():
    """Test score bounds [0.0, 1.0] for extreme combinations."""
    # All zeros -> 0.0
    assert calculate_flood_risk_score(0.0, 0.0, 0.0) == 0.0

    # All ones -> 1.0
    assert calculate_flood_risk_score(1.0, 1.0, 1.0) == 1.0

    # Intermediate test (0.50*0.5 + 0.25*0.5 + 0.25*0.5 = 0.5)
    score = calculate_flood_risk_score(0.5, 0.5, 0.5)
    assert score == 0.5

    # Clamping test for inputs exceeding range
    assert calculate_flood_risk_score(2.0, 5.0, 10.0) == 1.0
    assert calculate_flood_risk_score(-1.0, -2.0, -0.5) == 0.0


def test_directional_monotonicity():
    """Test that higher rainfall, lower elevation, and greater water proximity strictly increase risk."""
    # 1. Higher rainfall increases risk
    low_rain_score = calculate_flood_risk_score(rainfall_score=0.1, elevation_score=0.5, water_proximity_score=0.5)
    high_rain_score = calculate_flood_risk_score(rainfall_score=0.8, elevation_score=0.5, water_proximity_score=0.5)
    assert high_rain_score > low_rain_score

    # 2. Lower elevation (higher elevation_score) increases risk
    high_ground_score = calculate_flood_risk_score(rainfall_score=0.5, elevation_score=0.1, water_proximity_score=0.5)
    low_ground_score = calculate_flood_risk_score(rainfall_score=0.5, elevation_score=0.9, water_proximity_score=0.5)
    assert low_ground_score > high_ground_score

    # 3. Greater water proximity (higher water_proximity_score) increases risk
    inland_score = calculate_flood_risk_score(rainfall_score=0.5, elevation_score=0.5, water_proximity_score=0.1)
    coastal_score = calculate_flood_risk_score(rainfall_score=0.5, elevation_score=0.5, water_proximity_score=0.9)
    assert coastal_score > inland_score


def test_classify_risk_level():
    """Test standard categorical threshold classifications."""
    assert classify_risk_level(0.0) == "Low"
    assert classify_risk_level(0.299) == "Low"
    assert classify_risk_level(0.30) == "Moderate"
    assert classify_risk_level(0.599) == "Moderate"
    assert classify_risk_level(0.60) == "High"
    assert classify_risk_level(0.849) == "High"
    assert classify_risk_level(0.85) == "Severe"
    assert classify_risk_level(1.0) == "Severe"
