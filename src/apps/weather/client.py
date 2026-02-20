"""Weather data fetching using OpenWeatherMap API.

Note: This module uses the OpenWeatherMap 2.5 One Call API which is
available with free API keys. The 3.0 API requires a paid subscription.
"""

import logging
import math
from datetime import datetime
import requests

from src.settings.weather_scoring import (
    SEASONS,
    OPTIMAL_TEMPS,
    SEASONAL_WEIGHTS,
    TEMP_SIGMA,
    TRANSITION_DAYS,
    BOUNDARY_WEIGHT,
    PLATEAU_WEIGHT,
)


logger = logging.getLogger(__name__)

class WeatherClient:
    """
    Client for OpenWeatherMap 2.5 One Call API (free tier).

    Attributes:
        api_key: OpenWeatherMap API key.
        base_url: Base URL for One Call API 2.5.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5/forecast"

    def get_score_for_row(self, row):
        try:
            weather_data = self.get_weather(row['latitude'], row['longitude'])
            return self.compute_weather_score(weather_data)
        except Exception as e:
            logger.warning("Failed to get weather score for row: %s", e, exc_info=True)
            return None

    def get_weather(self, latitude: float, longitude: float):
        """
        Fetch weather data for given coordinates.

        Args:
            latitude: GPS latitude.
            longitude: GPS longitude.

        Returns:
            dict: Weather data with daily forecasts.

        Raises:
            requests.RequestException: If API request fails.
        """
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": self.api_key,
            "units": "metric",
        }

        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            raise requests.RequestException(
                f"Failed to fetch weather for {latitude}, {longitude}: "
                f"{str(e)}"
            ) from e

    def _get_season_weight(self, target_date: datetime) -> dict[str, float]:
        """Calculate seasonal weights using plateau system with overlapping transitions.

        Transitions are defined around season END boundaries for simpler logic.
        During the 30-day transition period, both adjacent seasons have non-zero weights
        that sum to 1.0.

        Args:
            target_date: Date to calculate weights for.

        Returns:
            dict: Mapping of season name to weight (0.0-1.0), with most seasons at 0.0
                  and up to 2 seasons with non-zero weights during transitions.

        Example at Aug 31 boundary (summer->autumn):
            - Day 229 (Aug 16): {'summer': 1.0, 'autumn': 0.0}  [start transition]
            - Day 244 (Aug 31): {'summer': 0.5, 'autumn': 0.5}  [boundary]
            - Day 259 (Sep 15): {'summer': 0.0, 'autumn': 1.0}  [end transition]
        """
        target_ordinal = target_date.toordinal()
        half_transition = TRANSITION_DAYS / 2

        season_order = ['winter', 'spring', 'summer', 'autumn']
        weights = {'winter': 0.0, 'spring': 0.0, 'summer': 0.0, 'autumn': 0.0}

        # FIRST PASS: Check END boundaries for transitions
        for i, season_name in enumerate(season_order):
            config = SEASONS[season_name]
            end_month, end_day = config['end']

            # Calculate season end date
            end_date = datetime(target_date.year, end_month, end_day)

            # Handle winter year wrap
            if season_name == 'winter':
                if target_date.month >= 12:
                    # December: winter ends next year
                    end_date = datetime(target_date.year + 1, end_month, end_day)
                elif target_date.month <= 3:
                    # Jan-Mar: winter ends this year (covers Feb 28 end + 15 days transition)
                    end_date = datetime(target_date.year, end_month, end_day)
                elif target_date.month >= 11:
                    # November: check transition to next year's winter end
                    end_date = datetime(target_date.year + 1, end_month, end_day)
                else:
                    # Apr-Oct: far from winter, skip
                    continue

            end_ordinal = end_date.toordinal()

            # Distance from season end boundary (in days)
            d = target_ordinal - end_ordinal

            # Check if we're in the transition zone around this season's END
            # Transition: [-15 days, +15 days] around the boundary (inclusive)
            if -half_transition <= d <= half_transition:
                # This season is exiting (weight goes from 1.0 to 0.0)
                # At d=-15: weight=1.0
                # At d=0: weight=0.5
                # At d=+15: weight=0.0
                outgoing_weight = BOUNDARY_WEIGHT - (d / TRANSITION_DAYS)
                weights[season_name] = max(0.0, min(1.0, outgoing_weight))

                # The next season is entering (weight goes from 0.0 to 1.0)
                next_season = season_order[(i + 1) % 4]
                incoming_weight = BOUNDARY_WEIGHT + (d / TRANSITION_DAYS)
                weights[next_season] = max(0.0, min(1.0, incoming_weight))

                # We've found the transition, return immediately
                return weights

        # SECOND PASS: Check for plateau (not in any transition)
        for season_name in season_order:
            config = SEASONS[season_name]
            start_month, start_day = config['start']
            end_month, end_day = config['end']

            # Calculate season boundaries
            start_date = datetime(target_date.year, start_month, start_day)
            end_date = datetime(target_date.year, end_month, end_day)

            # Handle winter year wrap
            if season_name == 'winter':
                if target_date.month >= 12:
                    start_date = datetime(target_date.year, start_month, start_day)
                    end_date = datetime(target_date.year + 1, end_month, end_day)
                elif target_date.month <= 2:
                    start_date = datetime(target_date.year - 1, start_month, start_day)
                    end_date = datetime(target_date.year, end_month, end_day)
                elif target_date.month >= 11:
                    start_date = datetime(target_date.year, start_month, start_day)
                    end_date = datetime(target_date.year + 1, end_month, end_day)
                else:
                    continue

            start_ordinal = start_date.toordinal()
            end_ordinal = end_date.toordinal()

            # Check if we're on plateau (past start transition, before end transition)
            # Use inclusive boundaries to avoid gaps (- 1 closes the leap-year off-by-one)
            if start_ordinal + half_transition - 1 <= target_ordinal <= end_ordinal - half_transition:
                weights[season_name] = PLATEAU_WEIGHT
                return weights

        # Fallback: shouldn't happen, raise error to catch configuration issues
        raise RuntimeError(
            f"No season found for {target_date.strftime('%Y-%m-%d')} "
            f"(ordinal {target_ordinal}). This indicates a bug in season configuration."
        )

    def _compute_temp_score(self, temp: float, optimal_temp: float) -> float:
        """Calculate temperature score using Gaussian distribution.

        Args:
            temp: Actual temperature in °C.
            optimal_temp: Optimal temperature for season in °C.

        Returns:
            float: Score in [0, 1] range.
        """
        return math.exp(-((temp - optimal_temp) ** 2) / (2 * TEMP_SIGMA ** 2))

    def compute_weather_score(self, weather_data: dict, target_date: datetime = None):
        """Calculate weather score using plateau seasonal weighting.

        Score based on 3 metrics with season-dependent weights:
        - Temperature (Gaussian score centered on optimal for season)
        - Precipitation probability (0-1, inverted)
        - Cloud coverage (0-100%, inverted)

        Args:
            weather_data: Weather API response with forecast list.
            target_date: Date for seasonal weight calculation (default: now).

        Returns:
            dict: Weather metrics and computed score, or None if no data.
        """
        forecast_list = weather_data.get("list", [])

        if not forecast_list:
            return None

        # Extract values
        temps = [item["main"]["temp"] for item in forecast_list]
        pop = [item.get("pop", 0) for item in forecast_list]
        clouds = [item["clouds"]["all"] for item in forecast_list]

        # Calculate averages
        avg_temp = sum(temps) / len(temps)
        avg_pop = sum(pop) / len(pop)
        avg_clouds = sum(clouds) / len(clouds)

        # Get seasonal weights for all seasons
        if target_date is None:
            target_date = datetime.now()
        season_weights = self._get_season_weight(target_date)

        # Find dominant season (highest weight)
        dominant_season = max(season_weights.items(), key=lambda x: x[1])[0]

        # Calculate component scores for each season, then blend
        temp_score_total = 0.0
        rain_score = 1 - avg_pop  # Less rain = higher score
        cloud_score = 1 - (avg_clouds / 100)  # Less clouds = higher score

        # Blend temperature scores across active seasons
        for season, season_weight in season_weights.items():
            if season_weight > 0:
                optimal_temp = OPTIMAL_TEMPS[season]
                temp_score = self._compute_temp_score(avg_temp, optimal_temp)
                temp_score_total += temp_score * season_weight

        # Use dominant season's weights for the final calculation
        weights = SEASONAL_WEIGHTS[dominant_season]

        # Weighted sum (normalize to [0, 100])
        final_score = (
            temp_score_total * weights['temperature'] +
            rain_score * weights['rain'] +
            cloud_score * weights['clouds']
        )

        # Format season weights for output (show non-zero only)
        active_seasons = {s: w for s, w in season_weights.items() if w > 0}

        return {
            "avg_temperature": round(avg_temp, 1),
            "avg_rain_probability": round(avg_pop * 100, 1),  # in %
            "avg_cloud_coverage": round(avg_clouds, 1),  # in %
            "weather_score": round(final_score, 1),
            "forecast_count": len(forecast_list),
            "season": dominant_season,
            "season_weights": {s: round(w, 2) for s, w in active_seasons.items()},
        }
