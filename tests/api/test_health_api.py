"""API tests for /api/health endpoint."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_health():
    """Verify system health endpoint returns 200 with telemetry summary."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["version"] in ("2.0.0", "5.0.0", "6.0.0")
    assert "database" in data
    assert "monitored_zones" in data
    assert "counts_by_risk" in data
