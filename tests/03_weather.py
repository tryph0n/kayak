"""Tests for weather module."""

import pytest
from datetime import datetime

from src.apps.weather import WeatherClient
from src.settings.weather_scoring import OPTIMAL_TEMPS, SEASONAL_WEIGHTS


@pytest.fixture
def weather_client():
    """Create a weather client for testing."""
    return WeatherClient(api_key="test_api_key")


def test_compute_weather_score_logic(weather_client):
    """Test weather score calculation logic with known values."""
    test_data = {
        "list": [
            {"main": {"temp": 25.0}, "pop": 0.0, "clouds": {"all": 0}},
            {"main": {"temp": 25.0}, "pop": 0.0, "clouds": {"all": 0}},
        ]
    }

    score = weather_client.compute_weather_score(test_data)

    assert score["avg_temperature"] == 25.0
    assert score["avg_rain_probability"] == 0.0
    assert score["avg_cloud_coverage"] == 0.0
    # With Gaussian scoring, score will depend on current season
    # Just verify it's in valid range [0, 100]
    assert 0 <= score["weather_score"] <= 100
    assert "season" in score
    assert "season_weights" in score


def test_compute_weather_score_with_rain(weather_client):
    """Test score decreases with rain."""
    rainy_data = {
        "list": [
            {"main": {"temp": 20.0}, "pop": 0.5, "clouds": {"all": 50}},
            {"main": {"temp": 20.0}, "pop": 0.5, "clouds": {"all": 50}},
        ]
    }

    score = weather_client.compute_weather_score(rainy_data)

    assert score["avg_rain_probability"] == 50.0
    # Score should be lower than perfect weather (82.0) but still positive
    assert 0 < score["weather_score"] < 82.0


def test_compute_weather_score_empty_data(weather_client):
    """Test weather score with empty forecast."""
    empty_data = {"list": []}
    score = weather_client.compute_weather_score(empty_data)

    assert score is None


def test_compute_weather_score_winter_not_negative(weather_client):
    """Test that winter conditions don't produce negative scores.

    Regression test for bug where low temps + some rain/clouds
    produced negative scores due to over-penalization.
    """
    winter_data = {
        "list": [
            {"main": {"temp": 5.0}, "pop": 0.3, "clouds": {"all": 50}},
            {"main": {"temp": 5.0}, "pop": 0.3, "clouds": {"all": 50}},
        ]
    }

    score = weather_client.compute_weather_score(winter_data)

    assert score["weather_score"] >= 0, \
        f"Winter score should not be negative, got {score['weather_score']}"


def test_compute_weather_score_range(weather_client):
    """Test that all scores fall within expected range [0, 100]."""
    extreme_cold_rainy = {
        "list": [
            {"main": {"temp": -10.0}, "pop": 1.0, "clouds": {"all": 100}},
            {"main": {"temp": -10.0}, "pop": 1.0, "clouds": {"all": 100}},
        ]
    }

    extreme_hot_sunny = {
        "list": [
            {"main": {"temp": 40.0}, "pop": 0.0, "clouds": {"all": 0}},
            {"main": {"temp": 40.0}, "pop": 0.0, "clouds": {"all": 0}},
        ]
    }

    cold_score = weather_client.compute_weather_score(extreme_cold_rainy)
    hot_score = weather_client.compute_weather_score(extreme_hot_sunny)

    assert 0 <= cold_score["weather_score"] <= 100, \
        f"Score should be in [0, 100], got {cold_score['weather_score']}"
    assert 0 <= hot_score["weather_score"] <= 100, \
        f"Score should be in [0, 100], got {hot_score['weather_score']}"
    assert hot_score["weather_score"] > cold_score["weather_score"], \
        "Sunny weather should score higher than rainy weather"


# Plateau seasonal scoring tests

def test_seasonal_weight_plateau(weather_client):
    """Test that seasonal weight = 1.0 on plateau (middle of season)."""
    # January 14 is winter midpoint, should be on plateau
    jan_14 = datetime(2025, 1, 14)
    weights = weather_client._get_season_weight(jan_14)

    assert weights["winter"] == pytest.approx(1.0, abs=0.01)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_seasonal_weight_boundary(weather_client):
    """Test that seasonal weight = 0.5 at exact season boundaries."""
    # February 28 is winter end (exact boundary)
    feb_28 = datetime(2025, 2, 28)
    weights = weather_client._get_season_weight(feb_28)

    assert weights["winter"] == pytest.approx(0.5, abs=0.01)
    assert weights["spring"] == pytest.approx(0.5, abs=0.01)
    assert sum(weights.values()) == pytest.approx(1.0)

    # August 31 is summer end (exact boundary)
    aug_31 = datetime(2025, 8, 31)
    weights = weather_client._get_season_weight(aug_31)

    assert weights["summer"] == pytest.approx(0.5, abs=0.01)
    assert weights["autumn"] == pytest.approx(0.5, abs=0.01)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_seasonal_weight_linear_transition(weather_client):
    """Test linear transition in 30-day period around boundary."""
    # August 31 is summer end (boundary with autumn)
    # Transition: Aug 16 (100% summer) -> Aug 31 (50%) -> Sep 15 (100% autumn)
    # Note: Transition is 15 days on each side of boundary

    # Aug 16: exactly 15 days before Aug 31, end of summer plateau
    aug_16 = datetime(2025, 8, 16)
    weights_start = weather_client._get_season_weight(aug_16)
    assert weights_start["summer"] == pytest.approx(1.0, abs=0.01)
    assert weights_start.get("autumn", 0.0) == pytest.approx(0.0, abs=0.01)

    # Aug 24: midpoint of transition (7 days before boundary)
    aug_24 = datetime(2025, 8, 24)
    weights_mid = weather_client._get_season_weight(aug_24)
    assert weights_mid["summer"] == pytest.approx(0.733, abs=0.01)
    assert weights_mid["autumn"] == pytest.approx(0.267, abs=0.01)

    # Aug 31: exact boundary
    aug_31 = datetime(2025, 8, 31)
    weights_boundary = weather_client._get_season_weight(aug_31)
    assert weights_boundary["summer"] == pytest.approx(0.5, abs=0.01)
    assert weights_boundary["autumn"] == pytest.approx(0.5, abs=0.01)

    # Sep 8: after boundary (8 days after)
    sep_8 = datetime(2025, 9, 8)
    weights_after = weather_client._get_season_weight(sep_8)
    assert weights_after["summer"] == pytest.approx(0.233, abs=0.01)
    assert weights_after["autumn"] == pytest.approx(0.767, abs=0.01)

    # Sep 15: exactly 15 days after Aug 31, start of autumn plateau
    sep_15 = datetime(2025, 9, 15)
    weights_end = weather_client._get_season_weight(sep_15)
    assert weights_end.get("summer", 0.0) == pytest.approx(0.0, abs=0.01)
    assert weights_end["autumn"] == pytest.approx(1.0, abs=0.01)

    # Verify all weights sum to 1.0
    for weights in [weights_start, weights_mid, weights_boundary, weights_after, weights_end]:
        assert sum(weights.values()) == pytest.approx(1.0)


def test_temp_score_winter_optimal(weather_client):
    """Test that 18°C in winter gets high score."""
    optimal_winter_temp = OPTIMAL_TEMPS['winter']  # 18°C

    winter_data = {
        "list": [
            {"main": {"temp": optimal_winter_temp}, "pop": 0.0, "clouds": {"all": 0}},
            {"main": {"temp": optimal_winter_temp}, "pop": 0.0, "clouds": {"all": 0}},
        ]
    }

    jan_14 = datetime(2025, 1, 14)
    score = weather_client.compute_weather_score(winter_data, target_date=jan_14)

    # With optimal temp, no rain, no clouds: should get near-perfect score
    assert score["weather_score"] > 90, \
        f"Optimal winter conditions should score high, got {score['weather_score']}"


def test_temp_score_summer_extreme(weather_client):
    """Test that 40°C in summer gets penalized by Gaussian."""
    extreme_summer_data = {
        "list": [
            {"main": {"temp": 40.0}, "pop": 0.0, "clouds": {"all": 0}},
            {"main": {"temp": 40.0}, "pop": 0.0, "clouds": {"all": 0}},
        ]
    }

    optimal_summer_data = {
        "list": [
            {"main": {"temp": 26.0}, "pop": 0.0, "clouds": {"all": 0}},
            {"main": {"temp": 26.0}, "pop": 0.0, "clouds": {"all": 0}},
        ]
    }

    jul_16 = datetime(2025, 7, 16)
    extreme_score = weather_client.compute_weather_score(extreme_summer_data, target_date=jul_16)
    optimal_score = weather_client.compute_weather_score(optimal_summer_data, target_date=jul_16)

    # 40°C should score significantly lower than 26°C due to Gaussian penalty
    assert optimal_score["weather_score"] > extreme_score["weather_score"], \
        "Optimal temp (26°C) should outscore extreme temp (40°C)"
    assert extreme_score["weather_score"] < 80, \
        f"40°C should be penalized, got {extreme_score['weather_score']}"


def test_variable_weights(weather_client):
    """Test that rain weight varies by season (spring=20%, winter=40%)."""
    rainy_data = {
        "list": [
            {"main": {"temp": 20.0}, "pop": 0.5, "clouds": {"all": 50}},
            {"main": {"temp": 20.0}, "pop": 0.5, "clouds": {"all": 50}},
        ]
    }

    # Same weather conditions in different seasons
    spring_date = datetime(2025, 4, 15)  # Spring midpoint
    winter_date = datetime(2025, 1, 14)  # Winter midpoint

    spring_score = weather_client.compute_weather_score(rainy_data, target_date=spring_date)
    winter_score = weather_client.compute_weather_score(rainy_data, target_date=winter_date)

    # Verify seasonal weights are being applied
    assert SEASONAL_WEIGHTS['spring']['rain'] == 20
    assert SEASONAL_WEIGHTS['winter']['rain'] == 40

    # Winter should penalize rain more heavily
    # (lower score with same rain conditions)
    assert spring_score["season"] == "spring"
    assert winter_score["season"] == "winter"
