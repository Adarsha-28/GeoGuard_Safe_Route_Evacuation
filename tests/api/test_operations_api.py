"""API tests for GeoGuard V4 Operational and Alert Endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.database.connection import SessionLocal
from backend.main import app
from backend.models.alert import Alert


@pytest.fixture
def client():
    return TestClient(app)


def test_get_operational_status(client):
    """Verify GET /api/operations/status returns real operational telemetry."""
    response = client.get("/api/operations/status")
    assert response.status_code == 200
    data = response.json()

    assert "weather_status" in data
    assert "model_version" in data
    assert "active_model" in data
    assert "fallback_active" in data
    assert "active_alerts" in data
    assert "high_risk_grids" in data
    assert "prediction_latency_ms" in data


def test_trigger_operational_cycle(client):
    """Verify POST /api/operations/run-cycle executes full pipeline on demand."""
    response = client.post("/api/operations/run-cycle")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("success", "skipped")
    if data["status"] == "success":
        assert data["total_grids"] > 0
        assert data["latency_ms"] >= 0.0


def test_get_active_alerts_and_acknowledgement(client):
    """Verify GET /api/alerts/active, GET /api/alerts/{id}, and POST /api/alerts/{id}/acknowledge."""
    # Create a test alert in DB
    with SessionLocal() as db:
        test_alert = Alert(
            title="Test Advisory Sector 10",
            severity="Warning",
            zone="Adyar",
            message="Moderate to High risk transition detected.",
            is_active=True,
            model_version="v3.0.0",
        )
        db.add(test_alert)
        db.commit()
        db.refresh(test_alert)
        alert_id = test_alert.id

    # 1. Verify GET /api/alerts/active includes our active alert
    resp_active = client.get("/api/alerts/active")
    assert resp_active.status_code == 200
    active_alerts = resp_active.json()
    assert any(a["id"] == alert_id for a in active_alerts)

    # 2. Verify GET /api/alerts/{id}
    resp_single = client.get(f"/api/alerts/{alert_id}")
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["id"] == alert_id
    assert single_data["zone"] == "Adyar"

    # 3. Acknowledge alert
    resp_ack = client.post(f"/api/alerts/{alert_id}/acknowledge")
    assert resp_ack.status_code == 200
    ack_data = resp_ack.json()
    assert "acknowledged" in ack_data["message"].lower()
    assert ack_data["alert"]["is_active"] is False

    # 4. Verify it is no longer in active alerts
    resp_active_after = client.get("/api/alerts/active")
    assert resp_active_after.status_code == 200
    assert not any(a["id"] == alert_id for a in resp_active_after.json())

    # Clean up test alert
    with SessionLocal() as db:
        db.query(Alert).filter(Alert.id == alert_id).delete()
        db.commit()


def test_health_api_component_breakdown(client):
    """Verify GET /api/health returns component status breakdown."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "components" in data
    comps = data["components"]
    assert "database" in comps
    assert "weather" in comps
    assert "ml_model" in comps
    assert "scheduler" in comps
    assert "application" in comps
