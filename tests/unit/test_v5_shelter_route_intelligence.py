"""Unit tests for GeoGuard V5 Shelter Intelligence and Route Intelligence Services."""

import pytest
from unittest.mock import MagicMock
from backend.services.route_intelligence_service import RouteIntelligenceService
from backend.services.shelter_intelligence_service import ShelterIntelligenceService


def test_shelter_intelligence_suitability_and_warning_status():
    """Verify shelter suitability score combines capacity headroom and surrounding flood risk."""
    service = ShelterIntelligenceService()
    mock_db = MagicMock()

    s1 = MagicMock()
    s1.id = 1
    s1.name = "Velachery Community Hall"
    s1.latitude = 12.98
    s1.longitude = 80.22
    s1.address = "Velachery Main Rd"
    s1.capacity = 500
    s1.available_capacity = 400
    s1.risk_level = "Low"
    s1.facilities = "Water, Medical"
    s1.contact = "044-123456"
    s1.is_active = True

    s2 = MagicMock()
    s2.id = 2
    s2.name = "Perumbakkam Relief Center"
    s2.latitude = 12.89
    s2.longitude = 80.19
    s2.address = "Perumbakkam"
    s2.capacity = 300
    s2.available_capacity = 0  # At capacity
    s2.risk_level = "High"
    s2.facilities = "Food"
    s2.contact = "044-654321"
    s2.is_active = True

    mock_db.query.return_value.filter.return_value.all.return_value = [s1, s2]
    service.risk_service.query_risk_by_coordinate = MagicMock(side_effect=lambda db, lat, lng: "Low" if lat > 12.9 else "High")

    evaluated = service.evaluate_shelters_intelligence(mock_db)

    assert len(evaluated) == 2
    res_s1 = next(s for s in evaluated if s["id"] == 1)
    res_s2 = next(s for s in evaluated if s["id"] == 2)

    assert res_s1["warning_status"] == "Optimal"
    assert res_s1["suitability_score"] > res_s2["suitability_score"]
    assert res_s2["warning_status"] == "At Capacity"


def test_route_intelligence_hazard_assessment():
    """Verify route evaluation calculates hazard exposure percentage and advisory status."""
    service = RouteIntelligenceService()
    mock_db = MagicMock()

    mock_shelter = MagicMock()
    mock_shelter.id = 1
    mock_shelter.name = "Sanctuary Shelter"
    mock_shelter.latitude = 13.05
    mock_shelter.longitude = 80.25
    mock_shelter.available_capacity = 100
    mock_shelter.risk_level = "Low"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_shelter

    # Mock OSRM returning 4 points
    service.routing_service.fetch_osrm_route = MagicMock(return_value={
        "distance": 5000.0,
        "duration": 600.0,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [80.20, 13.00],
                [80.22, 13.02],
                [80.24, 13.04],
                [80.25, 13.05],
            ],
        },
    })

    # Return Low risk for all points
    service.risk_service.query_risk_by_coordinate = MagicMock(return_value="Low")

    res = service.evaluate_route_intelligence(mock_db, src_lat=13.00, src_lng=80.20, shelter_id=1)

    assert res["shelter_id"] == 1
    assert res["maximum_flood_risk"] == "Low"
    assert res["percent_route_in_risky_zones"] == 0.0
    assert res["status"] == "Recommended"
    assert "advisory_disclaimer" in res
    assert res["safety_score"] >= 0.70
