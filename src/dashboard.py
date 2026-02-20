"""Streamlit dashboard for Kayak Travel Recommender.

This dashboard provides an interactive read-only interface to visualize
travel recommendations from PostgreSQL database.
"""

import streamlit as st
import pandas as pd
from sqlalchemy.orm import joinedload

from src.apps.database.client import DatabaseClient
from src.apps.database.models import Destination, Hotel
from src.apps.visualization.maps import create_top5_map, create_hotels_map
from src.settings import Settings


st.set_page_config(
    page_title="Kayak Travel Recommender",
    layout="wide",
)

st.title("Kayak Travel Recommender Dashboard")
st.markdown("Discover the best destinations and hotels in France based on weather data")


@st.cache_data
def load_data():
    """Load data from PostgreSQL database.

    Returns:
        tuple: (df_destinations, df_hotels) DataFrames

    Raises:
        Exception: If database query fails
    """
    db = DatabaseClient()
    session = db.get_session()

    try:
        # Query destinations
        destinations = session.query(Destination).all()
        df_destinations = pd.DataFrame(
            [
                {
                    "city_name": d.city_name,
                    "weather_score": d.weather_score,
                    "temperature": d.avg_temperature_7d,
                    "rain_prob": d.avg_rain_probability,
                    "cloud_coverage": d.avg_cloud_coverage,
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                }
                for d in destinations
            ]
        )

        # Query hotels with city information
        hotels = session.query(Hotel).options(joinedload(Hotel.destination)).all()
        df_hotels = pd.DataFrame(
            [
                {
                    "hotel_name": h.hotel_name,
                    "city_name": h.destination.city_name if h.destination else "Unknown",
                    "score": h.score,
                    "address": h.address,
                    "description": h.description,
                    "url": h.url,
                    "weather_score": h.destination.weather_score if h.destination else None,
                }
                for h in hotels
            ]
        )

        return df_destinations, df_hotels

    finally:
        session.close()
        db.close()


# Load data with caching
try:
    df_destinations, df_hotels = load_data()
except Exception as e:
    st.error(f"Error loading data from database: {e}")
    st.stop()

# KPIs
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Destinations", len(df_destinations))

with col2:
    st.metric("Total Hotels", len(df_hotels))

with col3:
    best_weather = (
        f"{df_destinations['weather_score'].max():.1f}"
        if not df_destinations.empty
        else "N/A"
    )
    st.metric("Best Weather Score", best_weather)

with col4:
    best_hotel = (
        f"{df_hotels['score'].max():.1f}/10" if not df_hotels.empty else "N/A"
    )
    st.metric("Best Hotel Score", best_hotel)

# Top Destinations section
st.header("Top Destinations")

if not df_destinations.empty:
    display_df_destinations = (
        df_destinations[
            ["city_name", "weather_score", "temperature", "rain_prob", "cloud_coverage"]
        ]
        .sort_values("weather_score", ascending=False)
        .head(Settings.top_n_destinations)
        .rename(
            columns={
                "city_name": "City",
                "weather_score": "Weather Score",
                "temperature": "Temperature (C)",
                "rain_prob": "Rain Probability (%)",
                "cloud_coverage": "Cloud Coverage (%)",
            }
        )
    )
    st.dataframe(display_df_destinations, hide_index=True)
else:
    st.info("No destinations data available")

try:
    fig_destinations = create_top5_map()
    st.plotly_chart(fig_destinations, use_container_width=True)
except Exception as e:
    st.error(f"Error generating destinations map: {e}")

# Top Hotels section
st.header("Top Hotels")

try:
    fig_hotels_map = create_hotels_map()
    st.plotly_chart(fig_hotels_map, use_container_width=True)
except Exception as e:
    st.error(f"Error generating hotels map: {e}")

if not df_hotels.empty:
    expected_hotels = Settings.top_n_destinations * Settings.hotels_per_destination

    # Build column list: include description only if it exists and has non-null values
    base_cols = ["hotel_name", "city_name", "score", "weather_score", "address"]
    if "description" in df_hotels.columns and df_hotels["description"].notna().any():
        base_cols.append("description")

    rename_map = {
        "hotel_name": "Hotel",
        "city_name": "City",
        "score": "Hotel Score",
        "weather_score": "Weather Score",
        "address": "Address",
        "description": "Description",
    }

    display_df_hotels = (
        df_hotels[base_cols]
        .sort_values("score", ascending=False)
        .head(expected_hotels)
        .rename(columns=rename_map)
    )
    st.dataframe(display_df_hotels, hide_index=True)
else:
    st.info("No hotels data available")

# Footer
st.markdown("---")
st.markdown("Data source: OpenWeatherMap + Booking.com | Built with Streamlit")
