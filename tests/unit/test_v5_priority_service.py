"""Unit tests for GeoGuard V5 Zone Prioritization Engine."""

import pytest
from unittest.mock import MagicMock
from backend.services.priority_service import PriorityService, PRIORITY_CATEGORY_THRESHOLDS


def test_priority_score_calculation_bounds_and_ranking():
    """Verify priority score is bounded in [0.0, 1.0] and sectors are ranked descending."""
    service = PriorityService()
    mock_db = MagicMock()

    # Mock predictions for 3 sectors
    service.forecast_service.predict_for_horizon = MagicMock(return_value=[
        {
            "grid_id": 1,
            "grid_name": "Velachery",
            "probability": 0.88,
            "risk_level": "Severe",
            "confidence": 0.90,
            "rainfall_mm": 60.0,
            "rainfall_3d_mm": 120.0,
            "features": {"latitude": 12.9815, "longitude": 80.2180},
        },
        {
            "grid_id": 2,
            "grid_name": "Mylapore",
            "probability": 0.20,
            "risk_level": "Low",
            "confidence": 0.80,
            "rainfall_mm": 5.0,
            "rainfall_3d_mm": 10.0,
            "features": {"latitude": 13.0368, "longitude": 80.2676},
        },
    ])

    service.risk_trend_service.get_grid_risk_trends = MagicMock(return_value={
        "overall_probability_delta": 0.15,
    })

    # Mock active shelters
    mock_shelter = MagicMock()
    mock_shelter.latitude = 12.98
    mock_shelter.longitude = 80.22
    mock_shelter.available_capacity = 250
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_shelter]

    priorities = service.calculate_priorities(mock_db, horizon="nowcast", persist=False)

    assert len(priorities) == 2
    # Check ranking
    assert priorities[0]["priority_rank"] == 1
    assert priorities[1]["priority_rank"] == 2
    assert priorities[0]["priority_score"] > priorities[1]["priority_score"]
    assert priorities[0]["priority_category"] in ("Critical", "High")
    assert priorities[1]["priority_category"] in ("Medium", "Low")

    for p in priorities:
        assert 0.0 <= p["priority_score"] <= 1.0
        assert "recommended_action" in p
        # Ensure no hallucinated population count is added
        assert "population" not in p


def test_priority_threshold_consistency():
    """Verify priority category definitions."""
    assert PRIORITY_CATEGORY_THRESHOLDS["Critical"] == 0.70
    assert PRIORITY_CATEGORY_THRESHOLDS["High"] == 0.50
    assert PRIORITY_CATEGORY_THRESHOLDS["Medium"] == 0.30
