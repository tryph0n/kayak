"""Geocoding service using Nominatim API."""

import time

import requests


class GeocodingClient:
    """Client for Nominatim geocoding API.

    Attributes:
        base_url: Base URL for Nominatim API.
        user_agent: User agent for API requests.
    """

    def __init__(self, user_agent: str = "kayak-recommender/1.0"):
        """Initialize the geocoding client.

        Args:
            user_agent: Custom user agent for API requests.
        """
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.user_agent = user_agent

    def get_coordinates(self, city: str, country: str = "France"):
        """Get GPS coordinates for a city.

        Args:
            city: City name.
            country: Country name (default: France).

        Returns:
            dict: Dictionary with 'latitude' and 'longitude' keys,
                  or None if not found.

        Raises:
            requests.RequestException: If API request fails.
        """
        params = {
            "q": f"{city}, {country}",
            "format": "json",
            "limit": 1,
        }

        headers = {"User-Agent": self.user_agent}

        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()

            if not data:
                return None

            return {
                "latitude": float(data[0]["lat"]),
                "longitude": float(data[0]["lon"]),
            }

        except requests.RequestException as e:
            raise requests.RequestException(
                f"Failed to geocode {city}: {str(e)}"
            ) from e

    def get_coordinates_batch(self, cities: list[str], delay: float = 1.0):
        """Get coordinates for multiple cities with rate limiting.

        Args:
            cities: List of city names.
            delay: Delay between requests in seconds (default: 1.0).

        Returns:
            dict: Dictionary mapping city names to coordinate dicts.
        """
        results = {}

        for city in cities:
            print(f"getting {city}")
            coords = self.get_coordinates(city)
            results[city] = coords

            if city != cities[-1]:
                time.sleep(delay)

        return results

    def geocode_address(self, address: str, city: str = None, country: str = "France"):
        """Geocode a full address string.

        Args:
            address: Full address string (e.g., "12 Rue de la Paix, Paris")
            city: Optional city name to include in query
            country: Country name (default: France)

        Returns:
            dict: Dictionary with 'latitude' and 'longitude' keys,
                  or None if not found.

        Raises:
            requests.RequestException: If API request fails.
        """
        # Build search query with address and optional city
        if city:
            query = f"{address}, {city}, {country}"
        else:
            query = f"{address}, {country}"

        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        }

        headers = {"User-Agent": self.user_agent}

        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()

            if not data:
                return None

            return {
                "latitude": float(data[0]["lat"]),
                "longitude": float(data[0]["lon"]),
            }

        except requests.RequestException as e:
            raise requests.RequestException(
                f"Failed to geocode address '{address}': {str(e)}"
            ) from e

    def geocode_hotels_batch(self, hotels_data: list[dict], delay: float = 1.0):
        """Geocode multiple hotels with rate limiting.

        Args:
            hotels_data: List of dicts with 'address' and optional 'city_name' keys
            delay: Delay between requests in seconds (default: 1.0)

        Returns:
            list: List of dicts with added 'latitude' and 'longitude' keys.
                  Failed geocoding results in None values.
        """
        results = []

        for i, hotel in enumerate(hotels_data):
            address = hotel.get("address")
            city_name = hotel.get("city_name")
            hotel_name = hotel.get("hotel_name", "Unknown")

            if not address:
                print(f"Warning: No address for hotel '{hotel_name}', skipping geocoding")
                results.append({**hotel, "latitude": None, "longitude": None})
                continue

            try:
                print(f"Geocoding hotel {i+1}/{len(hotels_data)}: {hotel_name}")
                coords = self.geocode_address(address, city=city_name)

                if coords:
                    results.append({**hotel, **coords})
                    print(f"  Success: ({coords['latitude']:.6f}, {coords['longitude']:.6f})")
                else:
                    print(f"  Failed: Address not found")
                    results.append({**hotel, "latitude": None, "longitude": None})

            except requests.RequestException as e:
                print(f"  Error: {str(e)}")
                results.append({**hotel, "latitude": None, "longitude": None})

            # Rate limiting
            if i < len(hotels_data) - 1:
                time.sleep(delay)

        return results
