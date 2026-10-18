"""API tests for /api/risk and weather synchronization endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_risk_by_grid_id():
    """Verify stored risk indices retrieval for sector ID."""
    response = client.get("/api/risk/1")
    assert response.status_code == 200
    data = response.json()
    assert "risk_level" in data
    assert "risk_score" in data
    assert data["probability"] is None  # No fake ML prediction in V2
    assert "rainfall_mm" in data


def test_get_risk_by_point():
    """Verify PostGIS spatial point lookup for Chennai coordinates."""
    response = client.get("/api/risk/point?lat=13.0418&lng=80.2341")
    assert response.status_code == 200
    data = response.json()
    assert data["latitude"] == 13.0418
    assert data["longitude"] == 80.2341
    assert data["risk_level"] in ("Low", "Moderate", "High", "Severe")


def test_get_risk_by_point_validation():
    """Verify input validation for out-of-range coordinates."""
    # Out of range latitude
    res_lat = client.get("/api/risk/point?lat=95.0&lng=80.0")
    assert res_lat.status_code == 400

    # Missing parameters
    res_missing = client.get("/api/risk/point?lat=13.0")
    assert res_missing.status_code == 422
