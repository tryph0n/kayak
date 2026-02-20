"""Main script to fetch city coordinates and weather data."""

import logging

import pandas as pd

from concurrent.futures import ThreadPoolExecutor
from src.settings import Settings
from src.core.constants import FRENCH_CITIES
from src.apps.geocoding import GeocodingClient
from src.apps.storage import S3Storage
from src.apps.weather import WeatherClient


logger = logging.getLogger(__name__)


def main():
    """Fetch geocoding and weather data, then upload to S3."""
    Settings.validate_required([
        "openweather_api_key",
        "aws_access_key_id",
        "aws_secret_access_key",
        "bucket",
    ])

    logger.info("Loading configuration...")

    s3 = S3Storage(
        bucket_name=Settings.bucket,
        aws_access_key_id=Settings.aws_access_key_id,
        aws_secret_access_key=Settings.aws_secret_access_key,
        region=Settings.s3_region,
    )

    coordinates_key = Settings.s3_coordinates_path
    if not s3.file_exists(coordinates_key):
        logger.info(f"Fetching data for {len(FRENCH_CITIES)} cities...")

        geocoding_client = GeocodingClient()

        logger.info("Geocoding cities...")
        coordinates = geocoding_client.get_coordinates_batch(FRENCH_CITIES)
        df_coord = pd.DataFrame.from_dict(coordinates, orient="index")
        df_coord.index.name = 'city_name'
        df_coord = df_coord.reset_index()

        # Validate city_name column
        assert 'city_name' in df_coord.columns, "Missing city_name column in coordinates DataFrame"
        assert df_coord['city_name'].nunique() == len(df_coord), "Duplicate city names found in coordinates DataFrame"
        assert len(df_coord) == len(FRENCH_CITIES), f"Expected {len(FRENCH_CITIES)} cities, got {len(df_coord)}"
        logger.info(f"OK Validated {len(df_coord)} cities with unique city_name values")

        logger.info("Uploading to S3...")
        s3.upload_dataframe(df_coord, coordinates_key)

    else:
        df_coord = s3.download_dataframe(coordinates_key)

    logger.info("Fetching weather data...")

    weather_client = WeatherClient(Settings.openweather_api_key)

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(
            weather_client.get_score_for_row,
            [row for _, row in df_coord.iterrows()]
        ))

        # Filter out failed cities (None results)
        valid_mask = [r is not None for r in results]
        skipped = sum(1 for v in valid_mask if not v)
        if skipped:
            logger.warning(f"Skipped {skipped} cities due to weather API errors")
        valid_results = [r for r in results if r is not None]

        results_df = pd.DataFrame(valid_results)
        results_df = results_df.rename(columns={'avg_temperature': 'avg_temperature_7d'})

        df_coord = df_coord[valid_mask].reset_index(drop=True)
        df_coord = pd.concat([df_coord, results_df], axis=1)


    df = df_coord.sort_values(by=["weather_score"], ascending=False)

    # Validate final DataFrame before upload
    assert 'city_name' in df.columns, "Missing city_name column in final DataFrame"
    assert df['city_name'].nunique() == len(df), "Duplicate city names in final DataFrame"
    logger.info(f"OK Final validation: {len(df)} cities with unique city_name values")

    logger.info("Uploading weather scored data to S3...")
    weather_key = Settings.s3_weather_scored_path

    s3.upload_dataframe(df, weather_key)

    print(f"OK Upload complete: s3://{Settings.bucket}/{weather_key}")
    print(f"\nProcessed {len(df)} cities successfully.")

    # Extract and save Top-N destinations
    df_top5 = df.head(Settings.top_n_destinations).copy()
    top5_columns = [
        'city_name',
        'latitude',
        'longitude',
        'weather_score',
        'avg_temperature_7d',
        'avg_rain_probability',
        'avg_cloud_coverage',
        'forecast_count'
    ]
    df_top5 = df_top5[top5_columns]

    logger.info(f"Uploading Top-{Settings.top_n_destinations} destinations to S3...")
    top5_key = Settings.s3_top5_destinations_path
    s3.upload_dataframe(df_top5, top5_key)

    print(f"\nOK Top-{Settings.top_n_destinations} destinations identified:")
    for idx, row in df_top5.iterrows():
        rank = df_top5.index.get_loc(idx) + 1
        print(f"{rank}. {row['city_name']} (score: {row['weather_score']:.1f})")
    print(f"OK Saved to: s3://{Settings.bucket}/{top5_key}")


if __name__ == "__main__":
    main()
