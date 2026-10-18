"""API tests for /api/predictions/flood and /api/grids model switching."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_predict_flood_risk_valid():
    """Verify POST /api/predictions/flood returns valid ML forecast envelope."""
    payload = {
        "latitude": 13.0418,
        "longitude": 80.2341,
        "rainfall_mm": 50.0,
    }
    response = client.post("/api/predictions/flood", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["latitude"] == 13.0418
    assert data["longitude"] == 80.2341
    assert data["prediction"] in ("Low", "Moderate", "High", "Severe")
    assert 0.0 <= data["probability"] <= 1.0
    assert "model_version" in data
    assert "contributing_features" in data
    assert len(data["contributing_features"]) > 0


def test_predict_flood_risk_validation():
    """Verify input validation handles invalid coordinates properly."""
    # Out-of-bounds latitude
    res_lat = client.post("/api/predictions/flood", json={"latitude": 99.0, "longitude": 80.0})
    assert res_lat.status_code == 422

    # Out-of-bounds longitude
    res_lng = client.post("/api/predictions/flood", json={"latitude": 13.0, "longitude": 200.0})
    assert res_lng.status_code == 422

    # Negative rainfall
    res_rain = client.post("/api/predictions/flood", json={"latitude": 13.0, "longitude": 80.0, "rainfall_mm": -10.0})
    assert res_rain.status_code == 422


def test_grids_model_switching():
    """Verify /api/grids supports switching between 'ml' and 'deterministic' engines."""
    # ML model query
    res_ml = client.get("/api/grids?model=ml")
    assert res_ml.status_code == 200
    data_ml = res_ml.json()
    assert data_ml.get("model") == "ml"
    first_feat_ml = data_ml["features"][0]
    assert "ml_probability" in first_feat_ml["properties"]

    # Deterministic baseline query
    res_det = client.get("/api/grids?model=deterministic")
    assert res_det.status_code == 200
    data_det = res_det.json()
    assert data_det.get("model") == "deterministic"
