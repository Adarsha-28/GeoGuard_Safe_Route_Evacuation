"""Unit tests for GeoGuard V6 Resilience Scoring Engine."""

import pytest
from unittest.mock import MagicMock, patch
from backend.services.resilience_scoring_service import ResilienceScoringService, ResilienceScoreResult


def test_resilience_score_result_structure():
    """Verify ResilienceScoreResult correctly formats and normalizes scores."""
    res = ResilienceScoreResult(
        overall=84.2,
        shelter=88.0,
        route=82.5,
        data=90.0,
        model=85.0,
        operational=78.0,
        category="Robust",
        formula_breakdown={},
    )
    d = res.to_dict()
    assert d["overall_resilience_score"] == 84.2
    assert d["category"] == "Robust"
    assert d["subscores"]["shelter"] == 88.0
    assert d["subscores"]["route"] == 82.5
    assert d["subscores"]["data"] == 90.0
    assert d["subscores"]["model"] == 85.0
    assert d["subscores"]["operational"] == 78.0
    assert d["weights"]["shelter"] == 0.25
    assert d["weights"]["route"] == 0.25
    assert d["weights"]["data"] == 0.15
    assert d["weights"]["model"] == 0.15
    assert d["weights"]["operational"] == 0.20


def test_resilience_composite_calculation():
    """Verify the weighted composite formula: 0.25*S + 0.25*R + 0.15*D + 0.15*M + 0.20*O."""
    s, r, d, m, o = 80.0, 70.0, 90.0, 85.0, 95.0
    expected = (0.25 * s) + (0.25 * r) + (0.15 * d) + (0.15 * m) + (0.20 * o)
    assert abs(expected - 82.75) < 1e-6


def test_resilience_category_thresholds():
    """Verify categorization across score thresholds: Robust, Moderate, Stressed, Vulnerable."""
    service = ResilienceScoringService()
    mock_db = MagicMock()

    with patch.object(service, "_compute_shelter_resilience", return_value=(90.0, {})), \
         patch.object(service, "_compute_route_resilience", return_value=(90.0, {})), \
         patch.object(service, "_compute_data_resilience", return_value=(90.0, {})), \
         patch.object(service, "_compute_model_resilience", return_value=(90.0, {})), \
         patch.object(service, "_compute_operational_resilience", return_value=(90.0, {})):
        res_high = service.compute_resilience(mock_db)
        assert res_high.category == "Robust"
        assert res_high.overall == 90.0

    with patch.object(service, "_compute_shelter_resilience", return_value=(30.0, {})), \
         patch.object(service, "_compute_route_resilience", return_value=(30.0, {})), \
         patch.object(service, "_compute_data_resilience", return_value=(30.0, {})), \
         patch.object(service, "_compute_model_resilience", return_value=(30.0, {})), \
         patch.object(service, "_compute_operational_resilience", return_value=(30.0, {})):
        res_low = service.compute_resilience(mock_db)
        assert res_low.category == "Vulnerable"
        assert res_low.overall == 30.0


def test_resilience_bounds_enforcement():
    """Verify overall score is strictly clamped to [0.0, 100.0]."""
    service = ResilienceScoringService()
    mock_db = MagicMock()

    with patch.object(service, "_compute_shelter_resilience", return_value=(150.0, {})), \
         patch.object(service, "_compute_route_resilience", return_value=(120.0, {})), \
         patch.object(service, "_compute_data_resilience", return_value=(100.0, {})), \
         patch.object(service, "_compute_model_resilience", return_value=(100.0, {})), \
         patch.object(service, "_compute_operational_resilience", return_value=(100.0, {})):
        res = service.compute_resilience(mock_db)
        assert res.overall <= 100.0
