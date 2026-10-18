"""API tests for /api/alerts endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_alerts():
    """Verify retrieving emergency alerts."""
    response = client.get("/api/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert isinstance(alerts, list)
    assert len(alerts) > 0


def test_create_alert_valid_and_validation():
    """Verify alert creation and schema validation."""
    payload = {
        "title": "Severe Cyclone Watch",
        "severity": "Critical",
        "zone": "Coastal Chennai",
        "message": "Storm surge expected along shoreline sectors.",
    }
    response = client.post("/api/alerts", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "alert" in data
    assert data["alert"]["title"] == "Severe Cyclone Watch"
    assert data["alert"]["severity"] == "Critical"

    # Invalid severity validation
    invalid_payload = {
        "title": "Test",
        "severity": "InvalidUnknownSeverity",
        "zone": "All",
        "message": "Test message",
    }
    res_bad = client.post("/api/alerts", json=invalid_payload)
    assert res_bad.status_code == 422

    # Missing fields
    res_missing = client.post("/api/alerts", json={"title": ""})
    assert res_missing.status_code == 422
