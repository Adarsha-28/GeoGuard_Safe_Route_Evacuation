"""Unit tests for GeoGuard V5 RiskTrendService and Prediction Change Detection."""

import pytest
from unittest.mock import MagicMock
from backend.services.risk_trend_service import RiskTrendService


def test_classify_trend_deterioration():
    """Verify state escalation and delta thresholds classify as DETERIORATING."""
    # Level jump Moderate -> High
    trend = RiskTrendService.classify_trend(
        prev_level="Moderate",
        curr_level="High",
        prev_prob=0.55,
        curr_prob=0.72,
    )
    assert trend == "DETERIORATING"

    # Probability delta >= 0.10 without level change
    trend2 = RiskTrendService.classify_trend(
        prev_level="Moderate",
        curr_level="Moderate",
        prev_prob=0.40,
        curr_prob=0.52,
    )
    assert trend2 == "DETERIORATING"


def test_classify_trend_sudden_deterioration():
    """Verify multi-level jump or massive probability spike triggers SUDDEN_DETERIORATION."""
    # Low -> High (jump of 2 levels)
    trend = RiskTrendService.classify_trend(
        prev_level="Low",
        curr_level="High",
        prev_prob=0.15,
        curr_prob=0.65,
    )
    assert trend == "SUDDEN_DETERIORATION"

    # Probability jump >= 0.35
    trend2 = RiskTrendService.classify_trend(
        prev_level="Moderate",
        curr_level="High",
        prev_prob=0.30,
        curr_prob=0.75,
    )
    assert trend2 == "SUDDEN_DETERIORATION"


def test_classify_trend_recovery_and_improving():
    """Verify recovery detection and gradual improvement classification."""
    # Severe -> Low with major drop
    trend_rec = RiskTrendService.classify_trend(
        prev_level="Severe",
        curr_level="Moderate",
        prev_prob=0.88,
        curr_prob=0.45,
    )
    assert trend_rec == "RECOVERY_DETECTED"

    # High -> Moderate gradual drop
    trend_imp = RiskTrendService.classify_trend(
        prev_level="High",
        curr_level="Moderate",
        prev_prob=0.70,
        curr_prob=0.58,
    )
    assert trend_imp == "IMPROVING"


def test_classify_trend_stable():
    """Verify unchanged risk levels with minor fluctuations remain STABLE."""
    trend = RiskTrendService.classify_trend(
        prev_level="Moderate",
        curr_level="Moderate",
        prev_prob=0.52,
        curr_prob=0.54,
    )
    assert trend == "STABLE"

    # None previous state is stable
    trend_none = RiskTrendService.classify_trend(
        prev_level=None,
        curr_level="Low",
        prev_prob=None,
        curr_prob=0.20,
    )
    assert trend_none == "STABLE"


def test_record_prediction_and_detect_delta():
    """Verify delta calculation and persistence object construction."""
    service = RiskTrendService()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    prediction_item = {
        "grid_id": 5,
        "grid_name": "Madipakkam",
        "prediction": "High",
        "probability": 0.76,
        "confidence": 0.88,
        "confidence_category": "High confidence",
        "rainfall_mm": 45.0,
        "rainfall_3d_mm": 90.0,
        "rainfall_7d_mm": 130.0,
        "model_version": "v5.0.0",
        "horizon": "nowcast",
        "is_fallback": False,
        "features": {},
        "contributing_features": [],
    }

    delta = service.record_prediction_and_detect_delta(mock_db, prediction_item, trigger_type="manual")

    assert delta.grid_id == 5
    assert delta.current_level == "High"
    assert delta.current_probability == 0.76
    assert delta.previous_probability is None
    assert delta.trend == "STABLE"  # initial is stable
    assert mock_db.add.called
