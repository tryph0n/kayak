#!/usr/bin/env python3
"""
Script to scrape hotels from top N destinations.
Downloads top destinations from S3, scrapes hotels, and uploads results back to S3.

Usage: python -m src.apps.scraping.run_top5
"""

import logging
import os
import tempfile

import pandas as pd
from scrapy.crawler import CrawlerProcess

from src.apps.scraping.booking import BookingPlaywrightSpider
from src.apps.storage.s3 import S3Storage
from src.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to orchestrate hotel scraping for top N destinations."""

    # Validate required settings
    logger.info("Validating configuration...")
    Settings.validate_required([
        'aws_access_key_id',
        'aws_secret_access_key',
        'bucket',
    ])

    # Initialize S3 client
    logger.info("Initializing S3 client...")
    s3 = S3Storage(
        bucket_name=Settings.bucket,
        aws_access_key_id=Settings.aws_access_key_id,
        aws_secret_access_key=Settings.aws_secret_access_key,
        region=Settings.s3_region,
    )

    # Download top destinations from S3
    logger.info(f"Downloading Top-{Settings.top_n_destinations} destinations from S3: {Settings.s3_top5_destinations_path}")

    if not s3.file_exists(Settings.s3_top5_destinations_path):
        logger.error(
            f"Top destinations file not found: {Settings.s3_top5_destinations_path}\n"
            "Please run 'make weather' first to generate the file."
        )
        return

    df_top5 = s3.download_dataframe(Settings.s3_top5_destinations_path)
    cities_to_scrape = df_top5['city_name'].tolist()

    logger.info(f"Cities to scrape: {', '.join(cities_to_scrape)}")

    # Create temporary file for Scrapy output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
        temp_csv_path = tmp_file.name

    try:
        # Configure Scrapy crawler
        logger.info("Configuring Scrapy crawler...")
        process = CrawlerProcess({
            'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'ROBOTSTXT_OBEY': False,
            'FEEDS': {
                temp_csv_path: {
                    'format': 'csv',
                    'encoding': 'utf8',
                    'overwrite': True,
                }
            },
            'LOG_LEVEL': 'INFO',
        })

        # Configure spider to scrape top-rated hotels
        # Use Booking.com sorting: by score/popularity
        BookingPlaywrightSpider.cities = cities_to_scrape
        BookingPlaywrightSpider.max_hotels = Settings.hotels_per_destination

        logger.info(f"Starting scraper for {len(cities_to_scrape)} cities...")
        logger.info(f"Max hotels per city: {Settings.hotels_per_destination}")
        logger.info(f"Expected total: {len(cities_to_scrape) * Settings.hotels_per_destination} hotels")
        logger.info("-" * 60)

        # Run the crawler
        process.crawl(BookingPlaywrightSpider)
        process.start()

        # Load scraped data
        logger.info(f"Loading scraped data from {temp_csv_path}...")
        df_hotels = pd.read_csv(temp_csv_path)

        # Validate and report results
        logger.info(f"Total hotels scraped: {len(df_hotels)}")

        # Count hotels per city
        hotels_per_city = df_hotels.groupby('city_name').size()
        logger.info("Hotels per city:")
        for city, count in hotels_per_city.items():
            logger.info(f"  - {city}: {count} hotels")

        # Upload to S3
        logger.info(f"Uploading results to S3: {Settings.s3_hotels_path}")
        s3.upload_dataframe(df_hotels, Settings.s3_hotels_path)

        logger.info("OK Hotel scraping completed successfully!")
        logger.info(f"Results available at: s3://{Settings.bucket}/{Settings.s3_hotels_path}")

    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        raise

    finally:
        # Clean up temporary file
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
            logger.info(f"Cleaned up temporary file: {temp_csv_path}")


if __name__ == '__main__':
    main()
