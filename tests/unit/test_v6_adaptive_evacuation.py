"""Unit tests for GeoGuard V6 Adaptive Evacuation and Route Resilience Services."""

import pytest
from unittest.mock import MagicMock
from backend.services.adaptive_evacuation_service import AdaptiveEvacuationService
from backend.services.route_resilience_service import RouteResilienceService


def test_shelter_stress_demand_factors():
    """Verify shelter stress evaluation scales demand under factors 1.0x, 1.25x, 1.5x, 2.0x."""
    service = AdaptiveEvacuationService()
    mock_db = MagicMock()

    mock_shelter = MagicMock()
    mock_shelter.id = 1
    mock_shelter.name = "Central Shelter"
    mock_shelter.capacity = 1000
    mock_shelter.available_capacity = 600  # occupied = 400
    mock_shelter.latitude = 13.08
    mock_shelter.longitude = 80.27
    mock_shelter.is_active = True

    mock_grid = MagicMock()
    mock_grid.id = 1
    mock_grid.latitude = 13.08
    mock_grid.longitude = 80.27
    mock_grid.flood_risk = "Low"

    mock_db.query.return_value.filter.return_value.all.return_value = [mock_shelter]
    mock_db.query.return_value.all.return_value = [mock_grid]

    # Test 1.0x
    results_1x = service.evaluate_shelter_stress(
        mock_db, simulated_sector_risks={1: "Low"}, simulation_demand_factor=1.0
    )
    assert len(results_1x) == 1
    res_1x = results_1x[0]
    assert res_1x["simulated_demand"] == 400
    assert res_1x["remaining_simulated_capacity"] == 600
    assert res_1x["stress_status"] == "NORMAL"

    # Test 2.0x (occupied * 2 = 800)
    results_2x = service.evaluate_shelter_stress(
        mock_db, simulated_sector_risks={1: "Low"}, simulation_demand_factor=2.0
    )
    res_2x = results_2x[0]
    assert res_2x["simulated_demand"] == 800
    assert res_2x["remaining_simulated_capacity"] == 200
    # Headroom = 200 / 1000 = 0.20 < 0.25 -> STRESSED
    assert res_2x["stress_status"] == "STRESSED"


def test_shelter_overloaded_status_and_alternative():
    """Verify shelter becomes OVERLOADED when remaining capacity < 0 and assigns alternative."""
    service = AdaptiveEvacuationService()
    mock_db = MagicMock()

    # Shelter 1 will be overloaded
    s1 = MagicMock()
    s1.id = 1
    s1.name = "Small Shelter"
    s1.capacity = 200
    s1.available_capacity = 50  # occupied = 150. at 2.0x demand -> 300 > 200
    s1.latitude = 13.08
    s1.longitude = 80.27
    s1.is_active = True

    # Shelter 2 has plenty of capacity
    s2 = MagicMock()
    s2.id = 2
    s2.name = "Large Relief Center"
    s2.capacity = 2000
    s2.available_capacity = 1800  # occupied = 200. at 2.0x demand -> 400 < 2000
    s2.latitude = 13.09
    s2.longitude = 80.28
    s2.is_active = True

    g = MagicMock()
    g.id = 1
    g.latitude = 13.08
    g.longitude = 80.27
    g.flood_risk = "Low"

    mock_db.query.return_value.filter.return_value.all.return_value = [s1, s2]
    mock_db.query.return_value.all.return_value = [g]

    results = service.evaluate_shelter_stress(
        mock_db, simulated_sector_risks={1: "Low"}, simulation_demand_factor=2.0
    )

    s1_res = next(r for r in results if r["shelter_id"] == 1)
    s2_res = next(r for r in results if r["shelter_id"] == 2)

    assert s1_res["stress_status"] == "OVERLOADED"
    assert s1_res["remaining_simulated_capacity"] < 0
    assert s1_res["alternative_shelter_id"] == 2
    assert s1_res["alternative_shelter_name"] == "Large Relief Center"

    assert s2_res["stress_status"] == "NORMAL"


def test_route_status_categorization():
    """Verify route evaluation yields AVAILABLE, CAUTION, UNSAFE, or BLOCKED_BY_SIMULATION."""
    service = RouteResilienceService()
    mock_db = MagicMock()

    grid = MagicMock()
    grid.id = 1
    grid.name = "Mylapore"
    grid.latitude = 13.03
    grid.longitude = 80.26
    grid.flood_risk = "Low"

    shelter = MagicMock()
    shelter.id = 10
    shelter.name = "Safe Haven"
    shelter.latitude = 13.05
    shelter.longitude = 80.27

    mock_db.query.return_value.filter.return_value.first.side_effect = [grid, shelter, None]
    mock_db.query.return_value.all.return_value = [grid]

    # Mock routing_service to return mock coordinates
    service.routing_service = MagicMock()
    service.routing_service.fetch_osrm_route.return_value = {
        "distance": 3500.0,
        "duration": 420.0,
        "geometry": {
            "coordinates": [
                [80.26, 13.03],
                [80.265, 13.04],
                [80.27, 13.05],
            ]
        },
    }

    # Case 1: Low risk -> AVAILABLE
    routes_low = service.evaluate_route_alternatives(
        mock_db, origin_grid_id=1, primary_shelter_id=10, backup_shelter_id=None, simulated_sector_risks={1: "Low"}
    )
    assert len(routes_low) == 3
    assert routes_low[0]["route_status"] == "AVAILABLE"
    assert routes_low[0]["route_role"] == "PRIMARY"
    assert routes_low[1]["route_role"] == "ALTERNATIVE_1"
    assert routes_low[2]["route_role"] == "ALTERNATIVE_2"

    # Reset side effect for next call
    mock_db.query.return_value.filter.return_value.first.side_effect = [grid, shelter, None]
    # Case 2: Severe risk -> BLOCKED_BY_SIMULATION
    routes_severe = service.evaluate_route_alternatives(
        mock_db, origin_grid_id=1, primary_shelter_id=10, backup_shelter_id=None, simulated_sector_risks={1: "Severe"}
    )
    assert routes_severe[0]["route_status"] == "BLOCKED_BY_SIMULATION"
    assert "BLOCKED_BY_SIMULATION denotes a simulated hazard blockage" in routes_severe[0]["advisory_message"]
