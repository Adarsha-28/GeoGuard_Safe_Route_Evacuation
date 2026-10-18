"""API integration and schema validation tests for all GeoGuard V5 REST endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_get_predictions_forecast_valid():
    """Verify GET /api/predictions/forecast returns valid schema across horizons."""
    for h in ["nowcast", "6h", "12h", "24h"]:
        resp = client.get(f"/api/predictions/forecast?horizon={h}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["horizon"] == h
        assert "total_grids" in data
        assert "predictions" in data
        if data["total_grids"] > 0:
            first = data["predictions"][0]
            assert "grid_id" in first
            assert "prediction" in first
            assert "probability" in first
            assert "confidence" in first
            assert "contributing_features" in first
            assert len(first["contributing_features"]) == 8


def test_get_predictions_forecast_invalid_horizon():
    """Verify GET /api/predictions/forecast returns 400 on invalid horizon."""
    resp = client.get("/api/predictions/forecast?horizon=48h")
    assert resp.status_code == 400
    assert "Invalid horizon" in resp.json()["error"]


def test_get_predictions_history():
    """Verify GET /api/predictions/history/{grid_id} returns history list."""
    resp = client.get("/api/predictions/history/1?horizon=nowcast&limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_risk_trends_valid_and_not_found():
    """Verify GET /api/risk/trends/{grid_id} returns trends and handles missing grid."""
    resp = client.get("/api/risk/trends/1?hours=24&horizon=nowcast")
    assert resp.status_code == 200
    data = resp.json()
    assert data["grid_id"] == 1
    assert "overall_trend" in data
    assert "history" in data

    # Test non-existent grid
    resp_404 = client.get("/api/risk/trends/99999")
    assert resp_404.status_code == 404


def test_get_priorities_filtering():
    """Verify GET /api/priorities returns triage rankings and supports filters."""
    resp = client.get("/api/priorities?horizon=nowcast")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_zones" in data
    assert "priorities" in data
    assert "critical_count" in data

    if data["total_zones"] > 0:
        first = data["priorities"][0]
        assert first["priority_rank"] == 1
        assert "priority_score" in first
        assert "priority_category" in first


def test_get_operations_timeline():
    """Verify GET /api/operations/timeline returns timeline events."""
    resp = client.get("/api/operations/timeline?hours=24&limit=20")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "events" in data


def test_get_shelters_intelligence():
    """Verify GET /api/shelters/intelligence returns suitability assessment."""
    resp = client.get("/api/shelters/intelligence")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_shelters" in data
    assert "shelters" in data
    if data["total_shelters"] > 0:
        first = data["shelters"][0]
        assert "suitability_score" in first
        assert "warning_status" in first
        assert "available_capacity" in first


def test_get_routes_intelligence_validation():
    """Verify GET /api/routes/intelligence validates coordinates and returns advisory."""
    # Test valid query to shelter 1
    resp = client.get("/api/routes/intelligence?src_lat=13.0827&src_lng=80.2707&shelter_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["shelter_id"] == 1
    assert "safety_score" in data
    assert "status" in data
    assert data["status"] in ("Recommended", "Caution", "Unsafe")
    assert "advisory_disclaimer" in data

    # Test invalid coordinate validation
    resp_err = client.get("/api/routes/intelligence?src_lat=100.0&src_lng=80.2707&shelter_id=1")
    assert resp_err.status_code == 400
