"""Unit tests for shelter distance and coordinate validation algorithms."""

import math
import pytest
from backend.services.shelter_service import haversine_distance, validate_coordinates


def test_haversine_distance():
    """Test standard distance calculations between known Chennai reference points."""
    # Distance from Chennai Central (13.0827, 80.2707) to T. Nagar (13.0418, 80.2341) ~ 6.1 km
    dist = haversine_distance(13.0827, 80.2707, 13.0418, 80.2341)
    assert 5.0 <= dist <= 7.5

    # Distance to identical point is 0.0
    assert haversine_distance(13.0827, 80.2707, 13.0827, 80.2707) == 0.0


def test_validate_coordinates():
    """Test coordinate validation for valid and invalid ranges."""
    # Valid
    valid, err = validate_coordinates(13.0827, 80.2707)
    assert valid is True
    assert err is None

    # Invalid latitude
    valid, err = validate_coordinates(95.0, 80.0)
    assert valid is False
    assert "Latitude" in err

    valid, err = validate_coordinates(-95.0, 80.0)
    assert valid is False

    # Invalid longitude
    valid, err = validate_coordinates(13.0, 185.0)
    assert valid is False
    assert "Longitude" in err

    # NaN / Inf
    valid, err = validate_coordinates(float("nan"), 80.0)
    assert valid is False

    valid, err = validate_coordinates(13.0, float("inf"))
    assert valid is False
