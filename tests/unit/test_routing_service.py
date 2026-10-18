"""Unit tests for routing service hazard evaluation algorithms."""

import pytest
from unittest.mock import MagicMock, patch

from backend.services.risk_service import RiskService
from backend.services.routing_service import RoutingService
from backend.services.shelter_service import ShelterService


def test_evaluate_route_risk():
    """Test composite scoring and risk penalty on mock route coordinates."""
    risk_service = RiskService()
    shelter_service = ShelterService()
    routing_service = RoutingService(risk_service=risk_service, shelter_service=shelter_service)

    mock_db = MagicMock()
    # Mock query_risk_by_coordinate to return Low
    with patch.object(risk_service, "query_risk_by_coordinate", return_value="Low"):
        mock_route = {
            "distance": 5000.0,  # 5 km
            "duration": 600.0,   # 10 mins
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [80.2341, 13.0418],
                    [80.2350, 13.0430],
                    [80.2360, 13.0440],
                ],
            },
        }

        mock_shelter = {
            "id": 1,
            "name": "Test Safe Shelter",
            "riskLevel": "Low",
            "availableCapacity": 100,
        }

        evaluation = routing_service.evaluate_route_risk(mock_db, mock_route, mock_shelter)

        assert "score" in evaluation
        assert 0.0 <= evaluation["score"] <= 1.0
        assert "safetyScore" in evaluation
        assert 0.0 <= evaluation["safetyScore"] <= 1.0
        assert evaluation["dist_km"] == 5.0
        assert evaluation["duration_mins"] == 10.0


def test_evaluate_route_severe_shelter_penalty():
    """Test that a shelter located in a Severe risk zone incurs safety penalty."""
    risk_service = RiskService()
    shelter_service = ShelterService()
    routing_service = RoutingService(risk_service=risk_service, shelter_service=shelter_service)
    mock_db = MagicMock()

    with patch.object(risk_service, "query_risk_by_coordinate", return_value="Low"):
        mock_route = {
            "distance": 3000.0,
            "duration": 400.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [[80.2341, 13.0418], [80.2350, 13.0430]],
            },
        }

        severe_shelter = {
            "id": 2,
            "name": "Flooded Shelter",
            "riskLevel": "Severe",
            "availableCapacity": 50,
        }

        safe_shelter = {
            "id": 3,
            "name": "Safe Shelter",
            "riskLevel": "Low",
            "availableCapacity": 50,
        }

        eval_severe = routing_service.evaluate_route_risk(mock_db, mock_route, severe_shelter)
        eval_safe = routing_service.evaluate_route_risk(mock_db, mock_route, safe_shelter)

        # Safe shelter score must be strictly higher than severe shelter score for identical geometry
        assert eval_safe["score"] > eval_severe["score"]
        assert eval_safe["safetyScore"] > eval_severe["safetyScore"]


def test_route_invalid_coordinates():
    """Test coordinate validation failure."""
    routing_service = RoutingService()
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        routing_service.calculate_safest_evacuation_route(mock_db, lat=95.0, lng=80.0)

    with pytest.raises(ValueError):
        routing_service.calculate_safest_evacuation_route(mock_db, lat=13.0, lng=200.0)
