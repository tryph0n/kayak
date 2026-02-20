# Configuration Guide

## Travel Recommendations Parameters

### Environment Variables

Configure the number of destinations and hotels in your `.env` file:

```bash
# Number of top destinations to analyze
TOP_N_DESTINATIONS=5

# Number of hotels to select per destination
HOTELS_PER_DESTINATION=4
```

### Default Values

If not specified in `.env`, these defaults are used:
- `TOP_N_DESTINATIONS`: **5**
- `HOTELS_PER_DESTINATION`: **4**
- Total hotels: **20** (5 destinations × 4 hotels)

### Examples

#### Scenario 1: Default Configuration
```bash
# .env
TOP_N_DESTINATIONS=5
HOTELS_PER_DESTINATION=4
```

**Result:**
- Weather pipeline selects **5 best destinations**
- Merger selects **4 top hotels per destination**
- Total: **20 hotels** (distributed: 4 per city)

#### Scenario 2: Smaller Dataset
```bash
# .env
TOP_N_DESTINATIONS=3
HOTELS_PER_DESTINATION=2
```

**Result:**
- Weather pipeline selects **3 best destinations**
- Merger selects **2 top hotels per destination**
- Total: **6 hotels** (distributed: 2 per city)

#### Scenario 3: Larger Dataset
```bash
# .env
TOP_N_DESTINATIONS=10
HOTELS_PER_DESTINATION=5
```

**Result:**
- Weather pipeline selects **10 best destinations**
- Merger selects **5 top hotels per destination**
- Total: **50 hotels** (distributed: 5 per city)

### Impact on Pipeline

These parameters affect:

1. **Weather Scoring** (`src/api/orchestration.py`)
   - Selects top N destinations by weather score
   - Saves to `kayak/processed/top5_destinations.csv`

2. **Hotel Scraping** (`src/apps/scraping/run_top5.py`)
   - Scrapes hotels for N selected destinations
   - Uses Playwright to extract Booking.com data

3. **Data Merger** (`src/apps/data/merger.py`)
   - Merges weather + hotel data
   - Selects M hotels **per destination** (not globally)
   - Ensures fair distribution across destinations

4. **Database** (`src/apps/database/verify.py`)
   - Stores N destinations
   - Stores N × M total hotels

5. **Visualizations** (`src/apps/visualization/`)
   - Maps adapt titles dynamically
   - Example: "Top-5 Destinations" → "Top-{N} Destinations"

6. **Dashboard** (`src/dashboard.py`)
   - UI reflects current configuration
   - Tab titles update automatically

### Important Note: Hotel Distribution

The system selects **M hotels per destination**, NOT M hotels globally.

**Example with TOP_N_DESTINATIONS=3 and HOTELS_PER_DESTINATION=4:**

✅ **Correct behavior:**
- Paris: 4 hotels
- Lyon: 4 hotels
- Marseille: 4 hotels
- **Total: 12 hotels**

❌ **Incorrect behavior (old logic):**
- Paris: 8 hotels (higher scores)
- Lyon: 3 hotels
- Marseille: 1 hotel
- **Total: 12 hotels** (unbalanced)

The new logic ensures each destination gets exactly M hotels, providing fair representation.

### Validation

Run the test suite to validate configuration:

```bash
uv run pytest tests/ -v
```

### Access in Code

```python
from src.settings import Settings

# Read current configuration
n_destinations = Settings.top_n_destinations
hotels_per_dest = Settings.hotels_per_destination
total_hotels = n_destinations * hotels_per_dest

print(f"Configuration: {n_destinations} destinations, {hotels_per_dest} hotels each")
print(f"Total hotels: {total_hotels}")
```
