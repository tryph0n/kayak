"""Streamlit page explaining the weather scoring system.

This page presents the scoring methodology based on a plateau system
and allows visualization of seasonal weights.
"""

import math
from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st
import numpy as np

from src.settings.weather_scoring import (
    OPTIMAL_TEMPS,
    SEASONAL_WEIGHTS,
    SEASONS,
    TEMP_SIGMA,
    TRANSITION_DAYS,
    BOUNDARY_WEIGHT,
    PLATEAU_WEIGHT,
)


st.set_page_config(
    page_title="Weather Scoring System",
    layout="wide",
)


def gaussian_temp_score(temperature: float, optimal_temp: float) -> float:
    """Compute the temperature score using a Gaussian curve.

    Args:
        temperature: Temperature in degrees C
        optimal_temp: Optimal temperature for the season

    Returns:
        Score between 0 and 1
    """
    return math.exp(-((temperature - optimal_temp) ** 2) / (2 * TEMP_SIGMA ** 2))


def day_of_year(month: int, day: int) -> int:
    """Convert a date (month, day) to day of year.

    Args:
        month: Month (1-12)
        day: Day of month

    Returns:
        Day of year (1-365)
    """
    # We use a non-leap year (365 days) as reference for day-of-year mapping.
    # In a leap year, Feb 29 (day 60) would shift all subsequent days by +1.
    # This does not affect scoring: the season boundaries are defined by ordinal
    # ranges and the plateau/transition logic handles the extra day seamlessly.
    date = datetime(2023, month, day)
    return date.timetuple().tm_yday


# Single WeatherClient instance reused across all seasonal_weight_for_day calls
from src.apps.weather.client import WeatherClient
_weather_client = WeatherClient("dummy")


def seasonal_weight_for_day(target_day: int, season_name: str) -> float:
    """Compute the weight of a season for a given day with overlapping transitions.

    This function implements the same logic as WeatherClient._get_season_weight
    but works with day-of-year integers (1-365) instead of datetime objects.

    Args:
        target_day: Day of year (1-365)
        season_name: Season name ('winter', 'spring', 'summer', 'autumn')

    Returns:
        Weight between 0.0 and 1.0

    Example at Aug 31 (day 243, summer->autumn boundary):
        - Day 228 (Aug 16): summer=1.0, autumn=0.0  [transition start]
        - Day 243 (Aug 31): summer=0.5, autumn=0.5  [boundary]
        - Day 258 (Sep 15): summer=0.0, autumn=1.0  [transition end]
    """
    # Convert target_day to a date in a non-leap year for visualization
    test_date = datetime.fromordinal(datetime(2023, 1, 1).toordinal() + target_day - 1)

    weights = _weather_client._get_season_weight(test_date)

    return weights.get(season_name, 0.0)


st.title("Weather Scoring System")

st.markdown("""
Our scoring system uses **Gaussian curves** to evaluate the weather quality
of a destination. This approach progressively penalizes deviations from ideal
conditions, unlike a linear score that would be too harsh or too lenient.

**Main advantage**: Moderate variations are tolerated (small penalty), but extremes
are heavily penalized, which better matches human perception of weather comfort.
""")


st.header("1. Temperature Score Curves")

st.markdown("""
Each season has an **optimal temperature** that receives the maximum score (100).
The further from this optimum, the lower the score, following a bell curve.
""")

# Compute temperature curves
temperatures = np.linspace(-10, 40, 500)
season_colors = {
    'winter': '#3498db',   # Blue
    'spring': '#2ecc71',   # Green
    'summer': '#e74c3c',   # Red
    'autumn': '#f39c12',   # Orange
}

season_names = {
    'winter': 'Winter',
    'spring': 'Spring',
    'summer': 'Summer',
    'autumn': 'Autumn',
}

fig_temp = go.Figure()

for season, optimal in OPTIMAL_TEMPS.items():
    scores = [gaussian_temp_score(t, optimal) * 100 for t in temperatures]
    fig_temp.add_trace(
        go.Scatter(
            x=temperatures,
            y=scores,
            name=season_names[season],
            line=dict(color=season_colors[season], width=3),
            hovertemplate='<b>%{fullData.name}</b><br>'
                          'Temperature: %{x:.1f}C<br>'
                          'Score: %{y:.1f}%<extra></extra>'
        )
    )

fig_temp.update_layout(
    title="Temperature Score by Season",
    xaxis_title="Temperature (C)",
    yaxis_title="Score Contribution (%)",
    hovermode='x unified',
    height=500,
    showlegend=True,
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="right",
        x=0.99
    )
)

st.plotly_chart(fig_temp, use_container_width=True)

# Dynamically compute the distance at which score = 50%
distance_50_pct = TEMP_SIGMA * math.sqrt(2 * math.log(2))

st.markdown(f"""
**Observations**:
- In summer, the optimum is {OPTIMAL_TEMPS['summer']}C (comfortable beach temperature)
- In winter, {OPTIMAL_TEMPS['winter']}C is preferred (mild temperatures)
- At +/-{distance_50_pct:.1f}C from the optimum, the score drops to 50%
- Extremes (heat wave or severe cold) are heavily penalized
""")


st.header("2. Seasonal Weight Evolution")

st.markdown("""
Seasons use a plateau system with linear transitions. The weight is 100%
at the middle of the season and decreases linearly to 50% at the boundaries
(transitions over 30 days).
""")

# Compute weights over 365 days
days = np.arange(1, 366)
season_weights_over_time = {}

for season in SEASONS.keys():
    weights = [seasonal_weight_for_day(d, season) for d in days]
    season_weights_over_time[season] = weights

fig_seasonal = go.Figure()

for season in ['winter', 'spring', 'summer', 'autumn']:
    fig_seasonal.add_trace(
        go.Scatter(
            x=days,
            y=season_weights_over_time[season],
            name=season_names[season],
            line=dict(color=season_colors[season], width=3),
            hovertemplate='<b>%{fullData.name}</b><br>'
                          'Day: %{x}<br>'
                          'Weight: %{y:.2f}<extra></extra>'
        )
    )

# Month annotations
month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

fig_seasonal.update_layout(
    title="Seasonal Weights Over the Year",
    xaxis_title="Day of Year",
    yaxis_title="Seasonal Weight (0-1)",
    hovermode='x unified',
    height=500,
    showlegend=True,
    xaxis=dict(
        tickmode='array',
        tickvals=month_starts,
        ticktext=month_names,
    ),
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="right",
        x=0.99
    )
)

st.plotly_chart(fig_seasonal, use_container_width=True)

half_transition = TRANSITION_DAYS / 2
st.markdown(f"""
**Observations**:
- Plateau at {PLATEAU_WEIGHT} at the middle of each season
- Weight = {BOUNDARY_WEIGHT} exactly at the boundaries between seasons
- Linear transitions over {TRANSITION_DAYS} days ({int(half_transition)} days on each side of the boundary)
- Simple and predictable system without complex curves
""")

# Visualization of 15-day transition zones
st.subheader("Zoom: 15-day transitions around boundaries")

st.markdown(f"""
The system uses linear transitions of **{int(half_transition)} days** before and after each seasonal boundary.
Here is a concrete example:
""")

# Example: Summer-Autumn transition (around Aug 31, day 243)
boundary_day = day_of_year(8, 31)  # Day 243
transition_start = boundary_day - int(half_transition)
transition_end = boundary_day + int(half_transition)

transition_days = np.arange(transition_start, transition_end + 1)
summer_weights_transition = [seasonal_weight_for_day(d, 'summer') for d in transition_days]
autumn_weights_transition = [seasonal_weight_for_day(d, 'autumn') for d in transition_days]

fig_transition = go.Figure()

fig_transition.add_trace(
    go.Scatter(
        x=transition_days,
        y=summer_weights_transition,
        name='Summer',
        line=dict(color=season_colors['summer'], width=3),
        hovertemplate='<b>Summer</b><br>Day: %{x}<br>Weight: %{y:.2f}<extra></extra>'
    )
)

fig_transition.add_trace(
    go.Scatter(
        x=transition_days,
        y=autumn_weights_transition,
        name='Autumn',
        line=dict(color=season_colors['autumn'], width=3),
        hovertemplate='<b>Autumn</b><br>Day: %{x}<br>Weight: %{y:.2f}<extra></extra>'
    )
)

# Vertical line at the boundary
fig_transition.add_vline(
    x=boundary_day,
    line_dash="dash",
    line_color="gray",
    annotation_text="Aug 31 (boundary)",
    annotation_position="top"
)

# Transition zones
fig_transition.add_vrect(
    x0=transition_start, x1=boundary_day,
    fillcolor="rgba(231, 76, 60, 0.1)",
    layer="below", line_width=0,
    annotation_text=f"Summer transition<br>({int(half_transition)}d)",
    annotation_position="top left"
)

fig_transition.add_vrect(
    x0=boundary_day, x1=transition_end,
    fillcolor="rgba(243, 156, 18, 0.1)",
    layer="below", line_width=0,
    annotation_text=f"Autumn transition<br>({int(half_transition)}d)",
    annotation_position="top right"
)

fig_transition.update_layout(
    title=f"Example: Summer-Autumn Transition (+/-{int(half_transition)} days around Aug 31)",
    xaxis_title="Day of Year",
    yaxis_title="Seasonal Weight",
    hovermode='x unified',
    height=400,
    showlegend=True,
    yaxis=dict(range=[0, 1.1]),
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01
    )
)

st.plotly_chart(fig_transition, use_container_width=True)

st.markdown(f"""
**Transition detail**:
- **Aug 16 to Aug 30** (15 days): Summer weight decreases linearly from {PLATEAU_WEIGHT} to {BOUNDARY_WEIGHT}
- **Aug 31**: Exact equilibrium point where summer = autumn = {BOUNDARY_WEIGHT}
- **Sep 1 to Sep 15** (15 days): Autumn weight increases linearly from {BOUNDARY_WEIGHT} to {PLATEAU_WEIGHT}
""")


st.header("3. Criterion Importance by Season")

st.markdown("""
Each season weights weather criteria (temperature, rain, clouds) differently
based on typical activities and traveler expectations.
""")

# Prepare data
seasons_list = ['winter', 'spring', 'summer', 'autumn']
seasons_en = [season_names[s] for s in seasons_list]

temp_weights = [SEASONAL_WEIGHTS[s]['temperature'] for s in seasons_list]
rain_weights = [SEASONAL_WEIGHTS[s]['rain'] for s in seasons_list]
cloud_weights = [SEASONAL_WEIGHTS[s]['clouds'] for s in seasons_list]

fig_weights = go.Figure()

# Colors by criterion: RED (temperature), BLUE (rain), GRAY (clouds)
criteria_colors = {
    'temperature': '#e74c3c',  # RED
    'rain': '#3498db',         # BLUE
    'clouds': '#7f8c8d',       # GRAY
}

fig_weights.add_trace(go.Bar(
    name='Temperature',
    x=seasons_en,
    y=temp_weights,
    marker_color=criteria_colors['temperature'],
    hovertemplate='<b>Temperature</b><br>%{y}%<extra></extra>'
))

fig_weights.add_trace(go.Bar(
    name='Rain',
    x=seasons_en,
    y=rain_weights,
    marker_color=criteria_colors['rain'],
    hovertemplate='<b>Rain</b><br>%{y}%<extra></extra>'
))

fig_weights.add_trace(go.Bar(
    name='Clouds',
    x=seasons_en,
    y=cloud_weights,
    marker_color=criteria_colors['clouds'],
    hovertemplate='<b>Clouds</b><br>%{y}%<extra></extra>'
))

fig_weights.update_layout(
    title="Weight Distribution by Season",
    xaxis_title="Season",
    yaxis_title="Importance (%)",
    barmode='stack',
    height=500,
    showlegend=True,
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="right",
        x=0.99
    )
)

st.plotly_chart(fig_weights, use_container_width=True)

st.markdown(f"""
**Observations**:
- **Winter**: Temperature ({SEASONAL_WEIGHTS['winter']['temperature']}%) + rain ({SEASONAL_WEIGHTS['winter']['rain']}%) prioritized -> avoid cold and rain
- **Spring**: Clouds ({SEASONAL_WEIGHTS['spring']['clouds']}%) important -> seeking sunshine for outdoor activities
- **Summer**: Temperature ({SEASONAL_WEIGHTS['summer']['temperature']}%) critical -> staying within the comfort range for outdoor activities
- **Autumn**: Temperature ({SEASONAL_WEIGHTS['autumn']['temperature']}%) + rain ({SEASONAL_WEIGHTS['autumn']['rain']}%) -> seeking Indian summer and dry weather
""")


st.header("4. Interactive Score Calculator")

st.markdown("""
Test the scoring system with your own weather values.
""")

col1, col2 = st.columns(2)

with col1:
    selected_season = st.selectbox(
        "Season",
        options=['winter', 'spring', 'summer', 'autumn'],
        format_func=lambda x: season_names[x],
        index=2  # Summer by default
    )

    temp_input = st.slider(
        "Temperature (C)",
        min_value=-10,
        max_value=40,
        value=OPTIMAL_TEMPS[selected_season],
        step=1
    )

    rain_input = st.slider(
        "Rain probability (%)",
        min_value=0,
        max_value=100,
        value=20,
        step=5
    )

    cloud_input = st.slider(
        "Cloud cover (%)",
        min_value=0,
        max_value=100,
        value=30,
        step=5
    )

with col2:
    # Compute score
    optimal_temp = OPTIMAL_TEMPS[selected_season]
    weights = SEASONAL_WEIGHTS[selected_season]

    # Temperature score (0-100)
    temp_score = gaussian_temp_score(temp_input, optimal_temp) * 100

    # Rain score (inverse linear: 0% rain = 100 pts, 100% rain = 0 pts)
    rain_score = 100 - rain_input

    # Cloud score (inverse linear)
    cloud_score = 100 - cloud_input

    # Weighted final score
    final_score = (
        temp_score * weights['temperature'] / 100 +
        rain_score * weights['rain'] / 100 +
        cloud_score * weights['clouds'] / 100
    )

    st.metric("Final Score", f"{final_score:.1f}/100")

    st.markdown("**Contribution breakdown:**")

    st.metric(
        f"Temperature (weight {weights['temperature']}%)",
        f"{temp_score:.1f}/100",
        delta=f"Contribution: {temp_score * weights['temperature'] / 100:.1f} pts"
    )

    st.metric(
        f"Rain (weight {weights['rain']}%)",
        f"{rain_score:.1f}/100",
        delta=f"Contribution: {rain_score * weights['rain'] / 100:.1f} pts"
    )

    st.metric(
        f"Clouds (weight {weights['clouds']}%)",
        f"{cloud_score:.1f}/100",
        delta=f"Contribution: {cloud_score * weights['clouds'] / 100:.1f} pts"
    )


st.header("5. Configuration Parameters")

st.markdown("""
The system is fully configurable via the constants file.
All parameters can be adjusted to fine-tune the scoring.
""")

st.code("""
src/settings/weather_scoring.py

Adjustable parameters:
- OPTIMAL_TEMPS: Optimal temperatures by season
- SEASONAL_WEIGHTS: Criterion weights (temperature, rain, clouds)
- TEMP_SIGMA: Width of the Gaussian temperature curve
- TRANSITION_DAYS: Duration of seasonal transitions (plateau)
- BOUNDARY_WEIGHT: Weight at the boundary between seasons
- PLATEAU_WEIGHT: Weight at the middle of the season
- SEASONS: Season start/end/midpoint dates
""", language="python")

# Dynamically compute the distance at which score = 50%
distance_for_50pct_score = TEMP_SIGMA * math.sqrt(2 * math.log(2))
boundary_pct = int(BOUNDARY_WEIGHT * 100)
plateau_pct = int(PLATEAU_WEIGHT * 100)

st.markdown(f"""
**Current values**:
- `TEMP_SIGMA` = {TEMP_SIGMA:.2f}C (score = 50% at +/-{distance_for_50pct_score:.1f}C)
- `TRANSITION_DAYS` = {TRANSITION_DAYS} days (total transition duration)
- `BOUNDARY_WEIGHT` = {BOUNDARY_WEIGHT} ({boundary_pct}% at boundaries)
- `PLATEAU_WEIGHT` = {PLATEAU_WEIGHT} ({plateau_pct}% at season midpoint)
""")

# Footer
st.markdown("---")
st.markdown("Plateau-based scoring system with transitions | Kayak Travel Recommender")
