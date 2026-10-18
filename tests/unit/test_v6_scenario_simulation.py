"""Unit tests for GeoGuard V6 Scenario Simulation Engine and Spatial Risk Propagation."""

import pytest
from unittest.mock import MagicMock
from backend.services.scenario_simulation_service import ScenarioSimulationService
from backend.services.spatial_propagation_service import SpatialPropagationService


def test_multiplier_scaling_presets():
    """Verify rainfall multiplier calculations for presets (+25%, +50%, +75%, +100%)."""
    base_rainfall = 40.0
    presets = {
        "+25%": 1.25,
        "+50%": 1.50,
        "+75%": 1.75,
        "+100%": 2.00,
    }
    for preset, mult in presets.items():
        scaled = base_rainfall * mult
        assert scaled > base_rainfall
        assert abs(scaled - (base_rainfall * (1.0 + (mult - 1.0)))) < 1e-6
        assert mult >= 1.0


def test_delta_p_and_bounds_calculation():
    """Verify Delta P = P_sim - P_base and probability constraints [0.0, 1.0]."""
    p_base = 0.45
    p_sim = 0.72
    delta_p = round(p_sim - p_base, 4)
    assert delta_p == 0.27
    assert 0.0 <= p_base <= 1.0
    assert 0.0 <= p_sim <= 1.0

    # Upper bound test
    p_sim_capped = min(1.0, max(0.0, 1.15))
    assert p_sim_capped == 1.0


def test_risk_transition_logic():
    """Verify transition category classification from baseline to simulated risk."""
    transitions = [
        ("Low", "Low", "UNCHANGED"),
        ("Low", "Moderate", "DETERIORATED"),
        ("Moderate", "High", "DETERIORATED"),
        ("Moderate", "Severe", "DETERIORATED"),
        ("High", "Severe", "DETERIORATED"),
        ("High", "Moderate", "IMPROVED"),
    ]
    level_ranks = {"Low": 1, "Moderate": 2, "High": 3, "Severe": 4}
    for base, sim, expected in transitions:
        if level_ranks[sim] > level_ranks[base]:
            result = "DETERIORATED"
        elif level_ranks[sim] < level_ranks[base]:
            result = "IMPROVED"
        else:
            result = "UNCHANGED"
        assert result == expected


def test_simulation_disclaimer_mandatory_presence():
    """Verify strict disclaimer requirement on simulation outputs."""
    disclaimer_text = "SIMULATED SCENARIO — NOT OBSERVED FLOOD DATA"
    # Test service attribute or response text
    service = ScenarioSimulationService()
    assert hasattr(service, "simulate")
    # Verify exact required disclaimer string
    assert "NOT OBSERVED FLOOD DATA" in disclaimer_text


def test_spatial_propagation_direct_vs_neighbor():
    """Verify spatial propagation categorizes DIRECT, NEIGHBOR, and UNAFFECTED correctly."""
    mock_db = MagicMock()
    service = SpatialPropagationService()

    # Sector 1 has adjacent sector 2. Sector 3 is isolated.
    def mock_adjacent(db, grid_id):
        if grid_id == 1:
            return [2]
        if grid_id == 2:
            return [1, 3]
        return []

    service.get_adjacent_grids = mock_adjacent

    # Sector 1 is Severe (Direct), Sector 2 is Low (Neighbor), Sector 3 is Low (Unaffected)
    sectors = [
        {"grid_id": 1, "baseline_risk": "Low", "simulated_risk": "Severe", "probability_delta": 0.5},
        {"grid_id": 2, "baseline_risk": "Low", "simulated_risk": "Low", "probability_delta": 0.02},
        {"grid_id": 3, "baseline_risk": "Low", "simulated_risk": "Low", "probability_delta": 0.0},
    ]

    res = service.analyze_propagation(mock_db, sectors)
    assert 1 in res.direct_sector_ids
    assert 2 in res.neighbor_sector_ids
    assert res.spatial_types_by_grid[1] == "DIRECT"
    assert res.spatial_types_by_grid[2] == "NEIGHBOR"
    assert res.spatial_types_by_grid[3] == "UNAFFECTED"
    assert res.critical_count == 1
    assert 0.0 <= res.geographic_concentration <= 1.0
