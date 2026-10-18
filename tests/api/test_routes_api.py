"""API tests for /api/routes and /api/evacuation endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_routes_safe_validation():
    """Verify input coordinate validation on /api/routes/safe."""
    # Missing payload fields
    res_empty = client.post("/api/routes/safe", json={})
    assert res_empty.status_code == 422

    # Non-number coordinates
    res_str = client.post("/api/routes/safe", json={"latitude": "north", "longitude": 80.0})
    assert res_str.status_code == 422

    # Out of range coordinates
    res_range = client.post("/api/routes/safe", json={"latitude": 99.0, "longitude": 80.0})
    assert res_range.status_code == 422


def test_evacuation_start_transaction():
    """Verify atomic shelter capacity decrement via /api/evacuation/start."""
    # First get current capacity of shelter 1
    shelter_before = client.get("/api/shelters/1").json()
    cap_before = shelter_before["availableCapacity"]

    response = client.post("/api/evacuation/start", json={"shelter_id": 1})
    assert response.status_code == 200
    data = response.json()
    assert "shelter" in data
    assert data["shelter"]["availableCapacity"] == cap_before - 1

    # Invalid shelter_id
    res_invalid = client.post("/api/evacuation/start", json={"shelter_id": 999999})
    assert res_invalid.status_code == 400
