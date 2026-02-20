"""Generate all Plotly visualizations.

This script generates both interactive maps:
- Top N destinations by weather score (configurable)
- Top hotels by score (configurable)

Usage:
    python -m src.apps.visualization.generate
    make visualize
"""

import os
import sys

from src.apps.visualization.maps import create_top5_map, create_top20_hotels_map
from src.settings import Settings


def generate_all_maps():
    """Generate all visualization maps.

    Creates the outputs/ directory if it doesn't exist, then generates
    both the top destinations and top hotels maps.

    Returns:
        bool: True if all maps generated successfully, False otherwise
    """
    try:
        # Ensure outputs directory exists
        os.makedirs("outputs", exist_ok=True)
        print("Generating visualizations...")
        print("-" * 50)

        # Generate top destinations map
        print(f"\n[1/2] Generating Top-{Settings.top_n_destinations} Destinations map...")
        fig_dest = create_top5_map()
        fig_dest.write_html("outputs/top5_destinations.html")
        print("OK Saved: outputs/top5_destinations.html")

        # Generate top hotels map
        expected_hotels = Settings.top_n_destinations * Settings.hotels_per_destination
        print(f"\n[2/2] Generating Top-{expected_hotels} Hotels map...")
        fig_hotels = create_top20_hotels_map()
        fig_hotels.write_html("outputs/top20_hotels.html")
        print("OK Saved: outputs/top20_hotels.html")

        print("\n" + "-" * 50)
        print("OK All visualizations generated successfully!")
        print("OK Files saved in: outputs/")
        print("  - top5_destinations.html")
        print("  - top20_hotels.html")

        return True

    except Exception as e:
        print(f"\nERROR Error generating visualizations: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = generate_all_maps()
    sys.exit(0 if success else 1)
