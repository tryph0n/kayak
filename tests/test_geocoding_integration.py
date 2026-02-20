"""Integration test for hotel geocoding functionality.

Tests the geocoding client with real hotel addresses.
"""

import pytest

from src.apps.geocoding.client import GeocodingClient


@pytest.mark.integration
def test_geocode_single_hotel_address():
    """Test geocoding a single hotel address."""
    geocoder = GeocodingClient()

    address = "rue du coma cheric 13, 66190 Collioure"
    city = "Collioure"

    result = geocoder.geocode_address(address, city=city, country="France")

    assert result is not None
    assert "latitude" in result
    assert "longitude" in result
    assert isinstance(result["latitude"], float)
    assert isinstance(result["longitude"], float)
    # Rough validation for France coordinates
    assert 41.0 <= result["latitude"] <= 51.0
    assert -5.0 <= result["longitude"] <= 10.0


@pytest.mark.integration
def test_geocode_hotels_batch():
    """Test batch geocoding of multiple hotels."""
    geocoder = GeocodingClient()

    hotels_data = [
        {
            "hotel_name": "Test Hotel 1",
            "address": "Place de la Comédie, Montpellier",
            "city_name": "Montpellier",
        },
        {
            "hotel_name": "Test Hotel 2",
            "address": "Rue de la Paix, Paris",
            "city_name": "Paris",
        },
    ]

    results = geocoder.geocode_hotels_batch(hotels_data, delay=1.0)

    assert len(results) == 2
    assert all("latitude" in h for h in results)
    assert all("longitude" in h for h in results)
    assert all("hotel_name" in h for h in results)


@pytest.mark.integration
def test_geocode_missing_address():
    """Test geocoding when address is missing."""
    geocoder = GeocodingClient()

    hotels_data = [
        {
            "hotel_name": "Hotel Without Address",
            "city_name": "Paris",
        }
    ]

    results = geocoder.geocode_hotels_batch(hotels_data, delay=1.0)

    assert len(results) == 1
    assert results[0]["latitude"] is None
    assert results[0]["longitude"] is None


@pytest.mark.integration
def test_geocode_invalid_address():
    """Test geocoding with an invalid/unfindable address."""
    geocoder = GeocodingClient()

    # Use a nonsensical address
    result = geocoder.geocode_address(
        "xyzabc123notarealaddress", city="Paris", country="France"
    )

    # Should return None for unfindable addresses
    assert result is None
