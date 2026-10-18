"""API tests for /api/shelters endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_all_shelters():
    """Verify listing all active relief shelters."""
    response = client.get("/api/shelters")
    assert response.status_code == 200
    shelters = response.json()
    assert isinstance(shelters, list)
    assert len(shelters) > 0
    first = shelters[0]
    assert "name" in first
    assert "availableCapacity" in first
    assert "riskLevel" in first


def test_get_shelter_by_id():
    """Verify single shelter lookup."""
    response = client.get("/api/shelters/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1

    # Not found
    res_404 = client.get("/api/shelters/999999")
    assert res_404.status_code == 404


def test_get_nearby_shelters_postgis():
    """Verify PostGIS database-side nearby shelter search."""
    response = client.get("/api/shelters/nearby?lat=13.0827&lng=80.2707&radius=25&limit=4")
    assert response.status_code == 200
    nearby = response.json()
    assert isinstance(nearby, list)
    assert len(nearby) > 0
    assert len(nearby) <= 4

    # Verify distances are ordered ascending
    distances = [s["distance"] for s in nearby if "distance" in s and s["distance"] is not None]
    assert distances == sorted(distances)


def test_get_nearby_shelters_validation():
    """Verify coordinate parameter validation."""
    response = client.get("/api/shelters/nearby?lat=invalid&lng=80.0")
    assert response.status_code == 422
