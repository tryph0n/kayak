"""Merge weather and hotels data to produce final travel recommendations."""

import pandas as pd

from src.apps.storage import S3Storage
from src.settings import Settings


def merge_weather_hotels() -> pd.DataFrame:
    """Merge weather scored data with hotels data and return top hotels per destination.

    This function:
    1. Downloads weather_scored.csv and hotels_top5.csv from S3
    2. Performs inner join on city_name
    3. Sorts by hotel score (descending)
    4. Selects top N hotels per destination (N from Settings.hotels_per_destination)
    5. Uploads final recommendations to S3

    Returns:
        pd.DataFrame: Top hotels per destination with weather and hotel data merged.

    Raises:
        Exception: If S3 operations fail or required settings are missing.
    """
    # Validate required settings
    Settings.validate_required([
        "aws_access_key_id",
        "aws_secret_access_key",
        "bucket",
    ])

    # Initialize S3 client
    s3 = S3Storage(
        bucket_name=Settings.bucket,
        aws_access_key_id=Settings.aws_access_key_id,
        aws_secret_access_key=Settings.aws_secret_access_key,
        region=Settings.s3_region,
    )

    print("Downloading weather scored data from S3...")
    df_weather = s3.download_dataframe(Settings.s3_weather_scored_path)
    print(f"OK Weather data: {len(df_weather)} cities")

    print("Downloading hotels data from S3...")
    df_hotels = s3.download_dataframe(Settings.s3_hotels_path)
    # Convert score to numeric (comes as string from scraper CSV)
    if "score" in df_hotels.columns:
        df_hotels["score"] = pd.to_numeric(df_hotels["score"], errors="coerce")
    print(f"OK Hotels data: {len(df_hotels)} hotels")

    # Inner join on city_name with suffixes for GPS columns
    print("Merging datasets on city_name...")
    df_merged = pd.merge(
        df_hotels,
        df_weather,
        on='city_name',
        how='inner',
        suffixes=('_hotel', '_city')
    )
    print(f"OK Merged data: {len(df_merged)} hotels")

    # Rename city GPS columns to be the primary lat/lon for ETL
    # (Destinations use city coordinates as primary; hotel coords are separate)
    df_merged = df_merged.rename(columns={
        'latitude_city': 'latitude',
        'longitude_city': 'longitude'
    })

    # Select top N hotels per destination
    # Group by city_name, sort by score within each group, take top N per destination
    df_top = (
        df_merged
        .sort_values(['city_name', 'score'], ascending=[True, False])
        .groupby('city_name', as_index=False)
        .head(Settings.hotels_per_destination)
    )

    # Sort final result by score descending for display
    df_top = df_top.sort_values('score', ascending=False)

    total_hotels = len(df_top)
    n_destinations = df_top['city_name'].nunique()
    print(f"OK Selected {total_hotels} hotels ({Settings.hotels_per_destination} per destination × {n_destinations} destinations)")
    print(f"   Score range: {df_top['score'].max():.1f} - {df_top['score'].min():.1f}")

    # Upload final recommendations to S3
    print("Uploading final recommendations to S3...")
    s3.upload_dataframe(df_top, Settings.s3_final_recommendations_path)
    print(f"OK Saved to: s3://{Settings.bucket}/{Settings.s3_final_recommendations_path}")

    # Display top 5 hotels
    print("\nTop-5 Hotels:")
    for idx, row in enumerate(df_top.head(5).itertuples(), 1):
        print(f"{idx}. {row.hotel_name} ({row.city_name}, score: {row.score:.1f})")

    return df_top


if __name__ == "__main__":
    merge_weather_hotels()
