"""Application settings and configuration.

This module provides centralized configuration management using environment variables.
All sensitive credentials are loaded from .env file.
"""

import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()


class Settings:
    """Application settings loaded from environment variables.

    Attributes:
        openweather_api_key: API key for OpenWeatherMap service.
        aws_access_key_id: AWS access key for S3 operations.
        aws_secret_access_key: AWS secret key for S3 operations.
        bucket: S3 bucket name for data storage.
        s3_region: AWS region for S3 (default: eu-west-3).
    """

    # OpenWeatherMap API configuration
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY")

    # AWS S3 configuration
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    bucket = os.getenv("BUCKET")
    s3_region = os.getenv("S3_REGION", "eu-west-3")

    # Travel recommendations configuration
    top_n_destinations = int(os.getenv("TOP_N_DESTINATIONS", "5"))
    hotels_per_destination = int(os.getenv("HOTELS_PER_DESTINATION", "4"))

    # S3 paths - Unified structure
    # Raw data: unprocessed data from external APIs
    s3_coordinates_path = "kayak/raw/coordinates.csv"

    # Processed data: calculated/cleaned data with scores
    s3_weather_scored_path = "kayak/processed/weather_scored.csv"
    s3_top5_destinations_path = "kayak/processed/top5_destinations.csv"
    s3_hotels_path = "kayak/processed/hotels_top5.csv"

    # Final data: enriched data ready for visualization
    s3_final_recommendations_path = "kayak/final/travel_recommendations.csv"

    # PostgreSQL NeonDB configuration
    postgres_host = os.getenv("POSTGRES_HOST")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_database = os.getenv("POSTGRES_DATABASE")
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    postgres_ssl_mode = os.getenv("POSTGRES_SSL_MODE", "require")

    @classmethod
    def get_postgres_url(cls) -> URL:
        """Build PostgreSQL connection URL for SQLAlchemy.

        Returns:
            SQLAlchemy URL object (handles special characters in password).

        Raises:
            ValueError: If required PostgreSQL environment variables are missing.
        """
        required = ["postgres_host", "postgres_database", "postgres_user", "postgres_password"]
        cls.validate_required(required)

        return URL.create(
            drivername="postgresql",
            username=cls.postgres_user,
            password=cls.postgres_password,
            host=cls.postgres_host,
            port=int(cls.postgres_port),
            database=cls.postgres_database,
            query={"sslmode": cls.postgres_ssl_mode} if cls.postgres_ssl_mode else {},
        )

    @classmethod
    def validate_required(cls, keys: list[str]) -> None:
        """Validate that required configuration keys are set.

        Args:
            keys: List of attribute names to validate.

        Raises:
            ValueError: If any required key is missing or empty.
        """
        missing = []
        for key in keys:
            value = getattr(cls, key, None)
            if not value:
                missing.append(key)

        if missing:
            env_vars = [key.upper() for key in missing]
            raise ValueError(
                f"Missing required environment variables: {', '.join(env_vars)}"
            )
