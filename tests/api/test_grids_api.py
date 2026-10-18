"""API tests for /api/grids endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_all_grids():
    """Verify retrieval of all Chennai grids as GeoJSON FeatureCollection."""
    response = client.get("/api/grids")
    assert response.status_code == 200
    data = response.json()
    assert data.get("type") == "FeatureCollection"
    assert len(data.get("features", [])) > 0


def test_get_grid_by_id():
    """Verify retrieval of specific grid by integer ID."""
    response = client.get("/api/grids/1")
    assert response.status_code == 200
    data = response.json()
    assert data.get("type") == "Feature"
    assert data.get("properties", {}).get("id") == 1

    # Invalid ID format
    response_invalid = client.get("/api/grids/not-an-int")
    assert response_invalid.status_code == 422

    # Not found ID
    response_missing = client.get("/api/grids/999999")
    assert response_missing.status_code == 404
