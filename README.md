# Kayak Travel Recommender
> Data pipeline that recommends travel destinations in France based on weather forecasts, hotel scraping, and adaptive Gaussian scoring -- served through an interactive Streamlit dashboard.

## Key Results

- End-to-end pipeline from raw API data to interactive travel recommendations
- Geocoding of 35 French cities + 5-day weather forecasts via OpenWeatherMap
- Adaptive Gaussian weather scoring with seasonal optimization (temperature, rain, cloud weights vary by season)
- Top-5 best-weather destinations + Top-20 highest-rated hotels (scraped from Booking.com)
- Interactive Plotly maps (destinations + hotels) and Folium visualizations
- All data persisted to AWS S3 and PostgreSQL (NeonDB)

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Package manager | uv |
| Scraping | Scrapy + Playwright (Booking.com) |
| Data processing | pandas, numpy |
| Storage | boto3 (AWS S3), SQLAlchemy + psycopg2 (PostgreSQL / NeonDB) |
| Visualization | Plotly, Folium |
| Dashboard | Streamlit |
| Testing | pytest |
| APIs | OpenWeatherMap, Nominatim (geocoding) |

## Architecture

**Data Lake (AWS S3)** -- S3 provides scalable object storage with no server management, cost-effective for CSV/batch workloads. Data flows through 3 zones:

- `raw/` -- Geocoded city coordinates from Nominatim API (`coordinates.csv`)
- `processed/` -- Scored, cleaned, and filtered data (Gaussian-scored cities, deduplicated hotels)
- `final/` -- Enriched, merged datasets ready for consumption (Top-5 destinations with Top-20 hotels)

Each zone acts as an immutable checkpoint: if a downstream step fails, upstream data is preserved and the step can be re-run independently.

**Data Warehouse (PostgreSQL / NeonDB)** -- Serverless PostgreSQL with a free tier, SSL encryption, and native SQL querying. The relational model fits the destinations-to-hotels one-to-many relationship naturally. NeonDB serves as the single source of truth for the Streamlit dashboard.

**Separation of concerns** -- S3 handles intermediate storage between pipeline steps (decoupling producers from consumers), while PostgreSQL serves structured queries from end users via the dashboard. The pipeline never queries S3 at read time from the frontend; all user-facing data goes through the warehouse.

**Flow:** APIs/Scraping -> S3 `raw/` -> Processing -> S3 `processed/` -> Merging -> S3 `final/` -> ETL -> PostgreSQL -> Dashboard

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys and services:
  - **OpenWeatherMap** -- API key ([register here](https://openweathermap.org/api))
  - **AWS** -- access key + secret key with S3 permissions
  - **PostgreSQL (NeonDB)** -- host, database, user, password ([free tier](https://neon.tech))
- Playwright browser install (Chromium, one-time setup)

## Installation

```bash
# Install dependencies
make setup

# Copy and fill in your API keys
cp .env.template .env
nano .env

# Install Playwright browsers (required for hotel scraping)
make setup-scraping

# Verify installation
make test
```

## Usage

Run the full pipeline (weather -> scrape -> merge -> etl -> visualize -> dashboard):

```bash
make all
```

Or run individual steps:

```bash
make weather          # Geocode cities, fetch forecasts, compute scores, generate Top-5
make scrape-hotels    # Scrape hotels from Top-5 destinations on Booking.com
make merge-data       # Merge weather + hotels data, produce Top-20 recommendations
make etl              # Load final data from S3 into PostgreSQL (NeonDB)
make verify-db        # Verify database integrity after ETL
make visualize        # Generate interactive Plotly HTML maps
make dashboard        # Start Streamlit dashboard at http://localhost:8501
```

Run `make help` for the full list of available commands.

## Data

All data flows through AWS S3 (raw -> processed -> final). Local output is written to `data/output/`. No data files are committed to the repository (gitignored). The pipeline is designed for local execution only -- there is no deployment target.

## Data Privacy

This project collects only publicly available data. No personal data is collected, stored, or processed at any point. There is no user tracking, no cookies, and no authentication of end users.

**Data sources and terms of use:**

- **OpenWeatherMap API** -- Public meteorological data, accessed via API key within free tier rate limits.
- **Nominatim / OpenStreetMap** -- Public geographic coordinates, subject to the [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/). A minimum 1-second delay between requests is enforced.
- **Booking.com** -- Public hotel listings (names, addresses, scores, descriptions) collected via Scrapy. `DOWNLOAD_DELAY` is set to 3 seconds and `CONCURRENT_REQUESTS` to 1 to minimize server load.

**Note on ROBOTSTXT_OBEY:** The Scrapy spider sets `ROBOTSTXT_OBEY = False` for Booking.com. This project is strictly academic (data engineering certification). The collected data is not redistributed, monetized, or used commercially. Rate limiting settings ensure minimal impact on the target server.

**GDPR / RGPD compliance:** Since no personal data is collected or processed, GDPR obligations related to personal data (consent, right of access, right to erasure) do not apply. All collected data points are publicly accessible information with no link to identifiable individuals.
