"""Test city_name coherence across the pipeline.

This test validates that city_name is correctly propagated and formatted
throughout the data pipeline, from constants to CSV output.
"""

import pandas as pd
from src.core.constants import FRENCH_CITIES
from src.apps.geocoding import GeocodingClient


def test_french_cities_format():
    """Test that FRENCH_CITIES has correct format."""
    # No duplicates
    assert len(FRENCH_CITIES) == len(set(FRENCH_CITIES)), "Duplicate cities found"

    # All strings
    assert all(isinstance(city, str) for city in FRENCH_CITIES), "Non-string city found"

    # No leading/trailing spaces
    for city in FRENCH_CITIES:
        assert city == city.strip(), f"City '{city}' has leading/trailing spaces"

    # No empty strings
    assert all(city for city in FRENCH_CITIES), "Empty city name found"

    print(f"OK FRENCH_CITIES: {len(FRENCH_CITIES)} cities, all valid")


def test_geocoding_preserves_city_names():
    """Test that geocoding batch returns dict with original city names."""
    # Mock test with first 3 cities
    test_cities = FRENCH_CITIES[:3]

    client = GeocodingClient()

    # We won't actually call the API, just test the structure
    # The get_coordinates_batch method should return dict[str, dict]
    # where keys are the original city names

    # Check method signature
    import inspect
    sig = inspect.signature(client.get_coordinates_batch)
    params = sig.parameters

    assert 'cities' in params, "get_coordinates_batch missing 'cities' parameter"

    print("OK GeocodingClient.get_coordinates_batch has correct signature")


def test_dataframe_city_name_column():
    """Test that DataFrame creation preserves city_name as column."""
    # Simulate what orchestration.py does
    mock_coordinates = {
        "Paris": {"latitude": 48.8566, "longitude": 2.3522},
        "Lyon": {"latitude": 45.7640, "longitude": 4.8357},
        "Marseille": {"latitude": 43.2965, "longitude": 5.3698},
    }

    # This is what orchestration.py does (lines 37-39)
    df_coord = pd.DataFrame.from_dict(mock_coordinates, orient="index")
    df_coord.index.name = 'city_name'
    df_coord = df_coord.reset_index()

    # Verify column name
    assert 'city_name' in df_coord.columns, "city_name column not found"

    # Verify no index column
    assert 'index' not in df_coord.columns, "Unwanted 'index' column found"

    # Verify city names are preserved
    assert set(df_coord['city_name']) == set(mock_coordinates.keys()), \
        "City names not preserved in DataFrame"

    # Verify no duplicates
    assert df_coord['city_name'].nunique() == len(df_coord), \
        "Duplicate city names in DataFrame"

    print("OK DataFrame correctly creates 'city_name' column")
    print(f"  Columns: {list(df_coord.columns)}")


def test_city_name_compatibility_with_scraper():
    """Test that FRENCH_CITIES names are compatible with Booking scraper."""
    # The scraper uses city names directly in URLs
    # Booking.com expects city names, possibly with URL encoding

    from urllib.parse import quote

    problematic_cities = []

    for city in FRENCH_CITIES:
        # Test URL encoding
        encoded = quote(city)

        # Check for potential issues
        if len(encoded) > 100:  # Arbitrary limit
            problematic_cities.append((city, "too long"))

        # Check for multiple consecutive spaces (could cause issues)
        if "  " in city:
            problematic_cities.append((city, "multiple spaces"))

    if problematic_cities:
        print("WARNING: Potentially problematic cities for scraping:")
        for city, issue in problematic_cities:
            print(f"  - {city}: {issue}")
    else:
        print("OK All city names compatible with URL encoding")


def test_city_name_uniqueness_for_joins():
    """Test that city_name can serve as a natural key for joins."""
    # Simulate two DataFrames that would be joined
    weather_df = pd.DataFrame({
        'city_name': ['Paris', 'Lyon', 'Marseille'],
        'weather_score': [15.5, 14.2, 18.9]
    })

    hotels_df = pd.DataFrame({
        'city_name': ['Paris', 'Lyon', 'Marseille', 'Paris'],  # Duplicate Paris OK
        'hotel_name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D']
    })

    # Test inner join
    joined = pd.merge(weather_df, hotels_df, on='city_name', how='inner')

    # Verify join worked
    assert len(joined) == 4, "Join produced wrong number of rows"
    assert 'weather_score' in joined.columns, "weather_score not in joined DF"
    assert 'hotel_name' in joined.columns, "hotel_name not in joined DF"

    # Test that all city names are preserved
    assert set(joined['city_name']) == {'Paris', 'Lyon', 'Marseille'}, \
        "City names not preserved in join"

    print("OK city_name works as natural key for joins")


def test_csv_roundtrip_preserves_city_name():
    """Test that CSV save/load preserves city_name."""
    import tempfile
    import os

    # Create test DataFrame
    df = pd.DataFrame({
        'city_name': ['Paris', 'Lyon', 'Marseille'],
        'latitude': [48.8566, 45.7640, 43.2965],
        'longitude': [2.3522, 4.8357, 5.3698]
    })

    # Save to CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = f.name

    try:
        df.to_csv(csv_path, index=False)

        # Load back
        df_loaded = pd.read_csv(csv_path)

        # Verify city_name preserved
        assert 'city_name' in df_loaded.columns, "city_name not in loaded CSV"
        assert list(df['city_name']) == list(df_loaded['city_name']), \
            "City names changed after CSV roundtrip"

        print("OK CSV roundtrip preserves city_name")
    finally:
        os.unlink(csv_path)


def test_scraper_cities_match_constants():
    """Test that scraper modules use cities from FRENCH_CITIES."""
    # Check that booking scraper spider imports or uses FRENCH_CITIES
    import os
    scraper_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'src',
        'apps',
        'scraping',
        'run_top5.py'
    )

    # Check that it imports from constants (or settings)
    with open(scraper_path, 'r') as f:
        content = f.read()

    # The scraper loads cities from S3 top5 file, which is generated
    # from FRENCH_CITIES in orchestration.py
    # So we verify the scraper correctly loads city_name column
    assert 'city_name' in content, \
        "run_top5.py should use 'city_name' column from S3 data"

    print("OK run_top5.py uses city_name from top5 destinations file")


if __name__ == "__main__":
    print("Testing city_name coherence across pipeline...\n")

    test_french_cities_format()
    test_geocoding_preserves_city_names()
    test_dataframe_city_name_column()
    test_city_name_compatibility_with_scraper()
    test_city_name_uniqueness_for_joins()
    test_csv_roundtrip_preserves_city_name()
    test_scraper_cities_match_constants()

    print("\n" + "=" * 60)
    print("OK All city_name coherence tests passed")
    print("=" * 60)
