"""API integration and schema validation tests for all GeoGuard V6 REST endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_get_resilience_baseline():
    """Verify GET /api/v6/resilience returns baseline 5-component resilience assessment."""
    resp = client.get("/api/v6/resilience")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_resilience_score" in data
    assert "category" in data
    assert "subscores" in data
    assert "weights" in data
    assert "formula" in data
    assert 0.0 <= data["overall_resilience_score"] <= 100.0

    sub = data["subscores"]
    for key in ["shelter", "route", "data", "model", "operational"]:
        assert key in sub
        assert 0.0 <= sub[key] <= 100.0


def test_post_scenario_simulation_lifecycle():
    """Verify full scenario lifecycle: simulate, list, fetch, sectors, shelters, routes, compare."""
    payload = {
        "name": "Integration Test Surge +50%",
        "rainfall_multiplier": 1.5,
        "horizon": "6h",
        "simulation_demand_factor": 1.25,
        "description": "Integration test run for V6 API",
        "operator": "Pytest Suite",
    }
    # 1. Simulate
    sim_resp = client.post("/api/v6/scenarios/simulate", json=payload)
    assert sim_resp.status_code == 200
    data = sim_resp.json()
    assert "scenario" in data
    assert "sectors" in data
    assert "shelters" in data
    assert "routes" in data
    assert "spatial_propagation" in data
    assert "resilience" in data
    assert "disclaimer" in data
    assert "SIMULATED SCENARIO" in data["disclaimer"]

    scenario_id = data["scenario"]["id"]
    assert scenario_id.startswith("scen_")

    # 2. List scenarios
    list_resp = client.get("/api/v6/scenarios?limit=10")
    assert list_resp.status_code == 200
    scenarios = list_resp.json()
    assert len(scenarios) > 0
    assert any(s["id"] == scenario_id for s in scenarios)

    # 3. Fetch single scenario
    get_resp = client.get(f"/api/v6/scenarios/{scenario_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == scenario_id

    # 4. Fetch sector results
    sec_resp = client.get(f"/api/v6/scenarios/{scenario_id}/sectors")
    assert sec_resp.status_code == 200
    sectors = sec_resp.json()
    assert len(sectors) > 0
    s0 = sectors[0]
    assert "grid_id" in s0
    assert "baseline_risk" in s0
    assert "simulated_risk" in s0
    assert "probability_delta" in s0
    assert "spatial_propagation_type" in s0

    # 5. Fetch shelter results
    sh_resp = client.get(f"/api/v6/scenarios/{scenario_id}/shelters")
    assert sh_resp.status_code == 200
    shelters = sh_resp.json()
    assert len(shelters) > 0
    sh0 = shelters[0]
    assert "shelter_name" in sh0
    assert "stress_status" in sh0
    assert sh0["stress_status"] in ("NORMAL", "STRESSED", "OVERLOADED")

    # 6. Fetch route results
    rt_resp = client.get(f"/api/v6/scenarios/{scenario_id}/routes")
    assert rt_resp.status_code == 200
    routes = rt_resp.json()
    assert len(routes) > 0
    rt0 = routes[0]
    assert "route_role" in rt0
    assert "route_status" in rt0
    assert rt0["route_status"] in ("AVAILABLE", "CAUTION", "UNSAFE", "BLOCKED_BY_SIMULATION")

    # 7. Fetch scenario comparison
    cmp_resp = client.get(f"/api/v6/scenarios/{scenario_id}/compare")
    assert cmp_resp.status_code == 200
    cmp_data = cmp_resp.json()
    assert "comparison_metrics" in cmp_data
    assert "disclaimer" in cmp_data
    metrics = cmp_data["comparison_metrics"]
    assert "baseline_critical_sectors" in metrics
    assert "simulated_critical_sectors" in metrics
    assert "resilience_delta" in metrics


def test_scenario_404_handling():
    """Verify 404 response on non-existent scenario ID."""
    resp = client.get("/api/v6/scenarios/scen_nonexistent_999")
    assert resp.status_code == 404

    resp_sec = client.get("/api/v6/scenarios/scen_nonexistent_999/sectors")
    assert resp_sec.status_code == 404


def test_decision_audit_log_endpoint():
    """Verify GET /api/v6/decision-log returns structured chronological audit trail."""
    resp = client.get("/api/v6/decision-log?limit=20")
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)
    if logs:
        first = logs[0]
        assert "event_type" in first
        assert "operator" in first
        assert "action_taken" in first
        assert "timestamp" in first


def test_failure_simulation_endpoint():
    """Verify POST /api/v6/resilience/failure-test triggers controlled fallback test."""
    payload = {"simulation_type": "WEATHER_API_UNAVAILABLE"}
    resp = client.post("/api/v6/resilience/failure-test", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["simulation_type"] == "WEATHER_API_UNAVAILABLE"
    assert data["fallback_activated"] is True
    assert data["audit_record_created"] is True
    assert "fallback_type" in data
    assert "details" in data
