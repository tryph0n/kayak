"""Visualization module for Kayak Travel Recommender.

This module provides interactive Plotly maps for:
- Top N destinations by weather score (configurable)
- Top hotels in top destinations (configurable)
"""

from src.apps.visualization.maps import create_top5_map, create_top20_hotels_map

__all__ = ["create_top5_map", "create_top20_hotels_map"]
