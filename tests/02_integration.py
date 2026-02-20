"""Integration tests to verify external APIs still work.

These tests make REAL API calls. Run with:
    pytest tests/ -v -s -m "integration"

Skip by default:
    pytest tests/ -v -m "not integration"
"""

import os

import pytest
from dotenv import load_dotenv

from src.apps.geocoding import GeocodingClient
from src.apps.weather import WeatherClient

load_dotenv()


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests"
)
def test_nominatim_api_still_works():
    """Verify Nominatim API responds correctly."""
    client = GeocodingClient()
    coords = client.get_coordinates("Paris", "France")

    assert coords is not None
    assert "latitude" in coords
    assert "longitude" in coords
    assert 48.0 < coords["latitude"] < 49.0
    assert 2.0 < coords["longitude"] < 3.0


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENWEATHER_API_KEY"),
    reason="OPENWEATHER_API_KEY not set"
)
def test_openweather_api_still_works():
    """Verify OpenWeatherMap API responds correctly."""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    client = WeatherClient(api_key)

    coords = {"latitude": 48.86, "longitude": 2.35}
    weather = client.get_weather(
        coords["latitude"],
        coords["longitude"]
    )

    EXPECTED_RES_COUNT = 40   # 1 forecast every 3 hours for 5 days: 5*24/3
    assert "cnt" in weather
    assert weather["cnt"] == EXPECTED_RES_COUNT
    assert len(weather["list"]) == EXPECTED_RES_COUNT
    assert "main" in weather["list"][0]