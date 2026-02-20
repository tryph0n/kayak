"""Interactive Plotly maps and charts for travel recommendations.

This module generates:
1. Top N destinations map ranked by weather score
2. Top hotels map ranked by score (with clustering, for HTML output)
3. Top hotels interactive map colored by city (for Streamlit)
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import joinedload

from src.apps.database.client import DatabaseClient
from src.apps.database.models import Destination, Hotel
from src.settings import Settings


def create_top5_map():
    """Create interactive map of top N destinations by weather score.

    Generates a Plotly Scattergeo map showing the best destinations in France
    based on weather scores. Uses fixed-size markers colored by weather score.

    Returns:
        plotly.graph_objects.Figure: Interactive map figure

    Raises:
        Exception: If database query fails
    """
    db = DatabaseClient()
    session = db.get_session()

    try:
        # Query top N destinations ordered by weather score
        top_destinations = (
            session.query(Destination)
            .order_by(Destination.weather_score.desc())
            .limit(Settings.top_n_destinations)
            .all()
        )

        if not top_destinations:
            raise ValueError("No destinations found in database")

        # Prepare data for visualization
        df = pd.DataFrame(
            [
                {
                    "city_name": d.city_name,
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                    "weather_score": d.weather_score,
                    "temperature": d.avg_temperature_7d,
                    "rain_prob": d.avg_rain_probability,
                    "cloud_coverage": d.avg_cloud_coverage,
                }
                for d in top_destinations
            ]
        )

        # Create Scattergeo map with fixed-size markers
        fig = go.Figure(
            go.Scattergeo(
                lon=df["longitude"],
                lat=df["latitude"],
                text=df["city_name"],
                mode="markers+text",
                marker=dict(
                    size=15,  # Fixed size for stable zoom
                    color=df["weather_score"],
                    colorscale="Viridis",
                    colorbar=dict(title="Weather Score"),
                    line=dict(width=2, color="white"),
                    showscale=True,
                    symbol="circle",
                ),
                textposition="top center",
                textfont=dict(size=12, color="black", family="Arial Black"),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Weather Score: %{customdata[0]:.1f}<br>"
                    "Temperature: %{customdata[1]:.1f}°C<br>"
                    "Rain Probability: %{customdata[2]:.0f}%<br>"
                    "Cloud Coverage: %{customdata[3]:.0f}%<br>"
                    "<extra></extra>"
                ),
                customdata=df[
                    ["weather_score", "temperature", "rain_prob", "cloud_coverage"]
                ].values,
            )
        )

        # Configure map layout (centered on France)
        fig.update_geos(
            scope="europe",
            center=dict(lat=46.5, lon=2.5),
            projection_scale=5,
            fitbounds="locations",  # Auto-adjust to fit markers
            showland=True,
            landcolor="lightgray",
            showlakes=True,
            lakecolor="lightblue",
            showcountries=True,
            countrycolor="white",
        )

        fig.update_layout(
            title=f"Top-{Settings.top_n_destinations} Destinations in France (by Weather Score)",
            height=600,
            width=1000,
            font=dict(family="Arial", size=14),
        )

        return fig

    finally:
        session.close()
        db.close()


def create_top20_hotels_map():
    """Create interactive map of top hotels in top destinations.

    Generates a Plotly Scattermap map with clustering showing the best hotels
    based on scores. Uses fixed-size square markers colored by hotel score.
    Hotels use city coordinates from the destinations table.

    Returns:
        plotly.graph_objects.Figure: Interactive map figure

    Raises:
        Exception: If database query fails
    """
    db = DatabaseClient()
    session = db.get_session()

    try:
        # Query top hotels with destination info
        expected_hotels = Settings.top_n_destinations * Settings.hotels_per_destination
        top_hotels = (
            session.query(Hotel)
            .options(joinedload(Hotel.destination))
            .order_by(Hotel.score.desc())
            .limit(expected_hotels)
            .all()
        )

        if not top_hotels:
            raise ValueError("No hotels found in database")

        # Prepare data for visualization using hotel-specific coordinates
        df = pd.DataFrame(
            [
                {
                    "hotel_name": h.hotel_name,
                    "city_name": h.destination.city_name,
                    "latitude": h.latitude if h.latitude else h.destination.latitude,
                    "longitude": h.longitude if h.longitude else h.destination.longitude,
                    "score": h.score,
                    "url": h.url,
                    "address": h.address,
                }
                for h in top_hotels
            ]
        )

        # Create Scattermap with clustering and color-coded markers
        fig = go.Figure(
            go.Scattermap(
                lon=df["longitude"],
                lat=df["latitude"],
                text=df["hotel_name"],
                mode="markers",
                marker=dict(
                    size=12,
                    color=df["score"],
                    colorscale="Viridis",
                    colorbar=dict(title="Hotel Score"),
                    showscale=True,
                ),
                cluster=dict(
                    enabled=True,
                    color="rgba(255, 0, 0, 0.6)",
                    size=[10, 20, 30, 40],
                    opacity=0.6,
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "City: %{customdata[1]}<br>"
                    "Score: %{customdata[2]:.1f}/10<br>"
                    "Address: %{customdata[3]}<br>"
                    "<extra></extra>"
                ),
                customdata=df[["hotel_name", "city_name", "score", "address"]].values,
            )
        )

        # Configure Scattermap layout centered on France
        expected_hotels = Settings.top_n_destinations * Settings.hotels_per_destination
        fig.update_layout(
            title=f"Top-{expected_hotels} Hotels in France (by Score)",
            height=600,
            width=1000,
            font=dict(family="Arial", size=14),
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=46.5, lon=2.5),
                zoom=6,
            ),
        )

        return fig

    finally:
        session.close()
        db.close()


def create_hotels_map():
    """Create interactive map of top hotels colored by city (for Streamlit).

    Queries the same set of hotels as create_top20_hotels_map. Each hotel is
    plotted at its own GPS coordinates (falls back to city coordinates if
    hotel-level coordinates are missing). Markers are colored by city using
    a discrete color palette. No clustering.

    Returns:
        plotly.graph_objects.Figure: Interactive Scattermap figure

    Raises:
        Exception: If database query fails
    """
    db = DatabaseClient()
    session = db.get_session()

    try:
        expected_hotels = Settings.top_n_destinations * Settings.hotels_per_destination
        top_hotels = (
            session.query(Hotel)
            .options(joinedload(Hotel.destination))
            .order_by(Hotel.score.desc())
            .limit(expected_hotels)
            .all()
        )

        if not top_hotels:
            raise ValueError("No hotels found in database")

        def _truncate(text, limit=150):
            if text is None:
                return "N/A"
            return text[:limit] + "..." if len(text) > limit else text

        df = pd.DataFrame(
            [
                {
                    "hotel_name": h.hotel_name,
                    "city_name": h.destination.city_name if h.destination else "Unknown",
                    "latitude": h.latitude if h.latitude else h.destination.latitude,
                    "longitude": h.longitude if h.longitude else h.destination.longitude,
                    "score": h.score,
                    "address": h.address or "N/A",
                    "description": _truncate(h.description),
                }
                for h in top_hotels
            ]
        )

        fig = px.scatter_map(
            df,
            lat="latitude",
            lon="longitude",
            color="city_name",
            hover_name="hotel_name",
            hover_data={
                "city_name": True,
                "score": ":.1f",
                "address": True,
                "description": True,
                "latitude": False,
                "longitude": False,
            },
            labels={
                "city_name": "City",
                "score": "Score",
                "address": "Address",
                "description": "Description",
            },
            title=f"Top-{expected_hotels} Hotels in Top Destinations",
            map_style="open-street-map",
            zoom=5,
            center={"lat": 46.5, "lon": 2.5},
            height=600,
        )

        fig.update_traces(marker=dict(size=14))

        return fig

    finally:
        session.close()
        db.close()
