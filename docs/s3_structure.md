# S3 Storage Structure

## Overview
This document describes the unified S3 storage structure for the Kayak Travel Recommender project.

## Directory Structure

```
kayak/
├── raw/              # Raw unprocessed data from external APIs
├── processed/        # Calculated and cleaned data with scores
└── final/            # Enriched data ready for visualization
```

## File Paths and Purpose

### Raw Data (`kayak/raw/`)
Unprocessed data directly from external APIs.

| File | Path | Content | Source | Updated By |
|------|------|---------|--------|------------|
| Coordinates | `kayak/raw/coordinates.csv` | City coordinates (lat, lon) for 35 French cities | Nominatim API | `orchestration.py` |
| Weather Raw | `kayak/raw/weather_raw.csv` | Raw weather data without scoring | OpenWeatherMap API | Not used (weather scoring is done directly) |

**Format**: CSV with columns varying by source.

---

### Processed Data (`kayak/processed/`)
Calculated and cleaned data with business logic applied.

| File | Path | Content | Input | Updated By |
|------|------|---------|-------|------------|
| Weather Scored | `kayak/processed/weather_scored.csv` | Cities with weather scores | Raw coordinates + weather API | `orchestration.py` |
| Top 5 Destinations | `kayak/processed/top5_destinations.csv` | Best 5 destinations by weather score | Weather scored data | `orchestration.py` |
| Hotels | `kayak/processed/hotels_top5.csv` | Hotel data for top 5 destinations | Booking.com scraping | `run_top5.py` |

**Format**: CSV with standardized columns and calculated fields.

**Key Columns in `weather_scored.csv`**:
- `city_name`: City name
- `latitude`, `longitude`: Coordinates
- `weather_score`: Calculated score (0-100)
- `avg_temperature_7d`: 7-day average temperature

---

### Final Data (`kayak/final/`)
Enriched data combining weather and hotel information, ready for visualization.

| File | Path | Content | Input | Updated By |
|------|------|---------|-------|------------|
| Travel Recommendations | `kayak/final/travel_recommendations.csv` | Complete travel recommendations with weather + hotels | Weather scored + hotels | `merger.py` |

**Format**: CSV with all necessary fields for Plotly visualizations.

**Expected Columns**:
- Weather fields: `city_name`, `latitude`, `longitude`, `weather_score`, `avg_temperature_7d`
- Hotel fields: `hotel_name`, `hotel_score`, `hotel_address`, `hotel_url`

---

## Configuration

All S3 paths are centralized in `src/settings/base.py`:

```python
class Settings:
    # Raw data
    s3_coordinates_path = "kayak/raw/coordinates.csv"
    # Processed data
    s3_weather_scored_path = "kayak/processed/weather_scored.csv"
    s3_top5_destinations_path = "kayak/processed/top5_destinations.csv"
    s3_hotels_path = "kayak/processed/hotels_top5.csv"

    # Final data
    s3_final_recommendations_path = "kayak/final/travel_recommendations.csv"
```

## Usage Example

```python
from src.settings import Settings
from src.apps.storage import S3Storage

# Initialize S3 client
s3 = S3Storage(
    bucket_name=Settings.bucket,
    aws_access_key_id=Settings.aws_access_key_id,
    aws_secret_access_key=Settings.aws_secret_access_key,
    region=Settings.s3_region,
)

# Upload data using centralized paths
s3.upload_dataframe(df, Settings.s3_weather_scored_path)

# Download data using centralized paths
df = s3.download_dataframe(Settings.s3_top5_destinations_path)
```

## Data Flow

```
1. GEOCODING
   Nominatim API → coordinates.csv (raw)

2. WEATHER SCORING
   coordinates.csv + OpenWeatherMap API → weather_scored.csv (processed)
   weather_scored.csv → top5_destinations.csv (processed)

3. HOTEL SCRAPING
   top5_destinations.csv + Booking.com → hotels_top5.csv (processed)

4. FINAL ENRICHMENT
   weather_scored.csv + hotels_top5.csv → travel_recommendations.csv (final)

5. VISUALIZATION
   travel_recommendations.csv → Plotly maps (Top-5 destinations, Top-20 hotels)
```

## Migration Notes

### Before (Inconsistent Paths)
- `PROJECTS/kayak/coordinates.csv` (mixed case, nested)
- `weather_data/cities_weather.csv` (different naming convention)

### After (Unified Structure)
- `kayak/raw/coordinates.csv` (raw data)
- `kayak/processed/weather_scored.csv` (processed data)

### Changes Applied
1. Updated `src/api/orchestration.py`:
   - Line 29: `coordinates_key = Settings.s3_coordinates_path`
   - Line 66: `weather_key = Settings.s3_weather_scored_path`

2. Added S3 paths to `src/settings/base.py` (lines 33-44)

### Benefits
- Single source of truth for all S3 paths
- Clear separation between raw, processed, and final data
- Easy to modify paths via Settings
- Consistent naming convention across the project
