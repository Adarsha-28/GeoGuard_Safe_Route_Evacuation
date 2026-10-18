"""Unit tests for GeoGuard V5 Confidence Reporting and Feature Attribution."""

import pytest
from backend.services.confidence_service import (
    compute_prediction_confidence,
    explain_prediction_features,
    MODEL_FEATURE_WEIGHTS,
)


def test_confidence_boundary_margin_monotonicity():
    """Verify confidence is higher when probability is further from 0.50 boundary."""
    # Near boundary: prob = 0.51 -> lower confidence
    conf_boundary, cat_boundary = compute_prediction_confidence(probability=0.51)
    # Far from boundary: prob = 0.95 -> higher confidence
    conf_extreme, cat_extreme = compute_prediction_confidence(probability=0.95)

    assert conf_extreme > conf_boundary
    assert cat_extreme == "High confidence"


def test_confidence_data_completeness_and_fallback_penalty():
    """Verify missing antecedent history or fallback mode penalizes confidence score."""
    conf_full, _ = compute_prediction_confidence(probability=0.85, has_7d_history=True, is_fallback=False)
    conf_fallback, _ = compute_prediction_confidence(probability=0.85, has_7d_history=False, is_fallback=True)

    assert conf_full > conf_fallback


def test_confidence_bounds_and_categories():
    """Ensure confidence outputs remain bounded in [0.0, 1.0] and categorizations are consistent."""
    for p in [0.0, 0.25, 0.5, 0.75, 1.0]:
        conf, cat = compute_prediction_confidence(p)
        assert 0.0 <= conf <= 1.0
        assert cat in ("High confidence", "Medium confidence", "Low confidence")


def test_explain_prediction_features_all_eight_predictors():
    """Verify explainability produces complete, structured attributions for all 8 predictors."""
    sample_features = {
        "rainfall_current_mm": 25.0,
        "rainfall_3d_accum_mm": 65.0,
        "rainfall_7d_accum_mm": 110.0,
        "elevation_m": 3.5,
        "distance_to_water_m": 220.0,
        "latitude": 12.9815,
        "longitude": 80.2180,
        "month": 11,
    }

    attributions = explain_prediction_features(sample_features, probability=0.82)
    assert len(attributions) == 8

    features_covered = {a["feature"] for a in attributions}
    expected = {
        "rainfall_current_mm",
        "rainfall_3d_accum_mm",
        "rainfall_7d_accum_mm",
        "elevation_m",
        "distance_to_water_m",
        "latitude",
        "longitude",
        "month",
    }
    assert features_covered == expected

    # Verify descending ordering by model feature importance
    importances = [a["relative_importance"] for a in attributions]
    assert importances == sorted(importances, reverse=True)
