"""Weather scoring configuration.

All constants configurable here for easy tuning.
"""

import math

# Seasonal definitions (meteorological)
# Each season has start/end dates and a midpoint for plateau weighting
SEASONS = {
    'winter': {
        'start': (12, 1),   # December 1
        'end': (2, 28),     # February 28 (89 days, non-leap)
        'midpoint': (1, 14) # January 14 (midpoint of 89-day season)
    },
    'spring': {
        'start': (3, 1),    # March 1
        'end': (5, 31),     # May 31 (91 days)
        'midpoint': (4, 15) # April 15
    },
    'summer': {
        'start': (6, 1),    # June 1
        'end': (8, 31),     # August 31 (91 days)
        'midpoint': (7, 16) # July 16
    },
    'autumn': {
        'start': (9, 1),    # September 1
        'end': (11, 30),    # November 30 (90 days)
        'midpoint': (10, 16) # October 16
    },
}

# Optimal temperatures (°C) by season (from HCI research)
# These represent ideal temperatures that get maximum score
OPTIMAL_TEMPS = {
    'winter': 16.0,   # Warm temps wanted in winter
    'spring': 20,   # Mild temps OK in spring
    'summer': 26,   # 24-28°C ideal range for summer
    'autumn': 22,   # Indian summer (warm autumn)
}

# Scoring weights by season (must sum to 100)
# Temperature, rain, and clouds have different importance per season
SEASONAL_WEIGHTS = {
    'winter': {
        'temperature': 50,  # Want warm temps
        'rain': 40,         # NO rain wanted (snow/cold rain)
        'clouds': 10        # Clouds less important
    },
    'spring': {
        'temperature': 40,  # Moderate temps OK
        'rain': 20,         # Light showers acceptable
        'clouds': 40        # Want sun (flowers, nature)
    },
    'summer': {
        'temperature': 60,  # Ideal temp range critical
        'rain': 30,         # Rain ruins beach/outdoor
        'clouds': 10        # Some clouds OK (shade)
    },
    'autumn': {
        'temperature': 50,  # Indian summer (warm)
        'rain': 35,         # Dry weather wanted
        'clouds': 15        # Some clouds OK
    },
}

# Sigma controls the "width" of the Gaussian bell curve.
# Smaller sigma = steep drop (penalties harsh)
# Larger sigma = gentle drop (penalties lenient)
#
# In our case:
# - Sigma determines how quickly temp score drops from optimal
# - At distance = sigma: score = exp(-0.5) ~ 0.61 (61%)
# - At distance = 2*sigma: score = exp(-2) ~ 0.14 (14%)
#
# Constraint: score = 0.5 at ±10°C from optimal temperature
# Calculation from Gaussian formula: weight = exp(-(distance²) / (2*sigma²))
# Setting weight = 0.5 at distance = 10:
#   0.5 = exp(-(10²) / (2*sigma²))
#   ln(0.5) = -100 / (2*sigma²)
#   sigma² = 100 / (2*ln(2))
#   sigma = 10 / sqrt(2*ln(2))
#
# Result: At 26°C optimal (summer), 16°C and 36°C both get score = 0.5
TEMP_SIGMA = 10.0 / math.sqrt(2 * math.log(2))  # ~ 8.5°C

# Plateau system with linear transitions at season boundaries.
#
# System design:
# - Weight = 1.0 (100%) on plateau in middle of season
# - Weight = 0.5 (50%) at exact season boundary
# - Linear transition over 30 days centered on boundary
#
# Example: Summer ends Aug 31, Fall starts Sep 1
# - Aug 16 to Sep 15 = transition period (30 days centered on Sep 1)
# - Aug 16: 100% summer -> linear transition -> 50% at Sep 1
# - Sep 1 to Sep 15: 50% fall -> linear transition -> 100% at Sep 15
#
# This creates smooth handoffs between seasons without complex math.
TRANSITION_DAYS = 30  # Total transition period around boundary
BOUNDARY_WEIGHT = 0.5  # Weight at exact boundary
PLATEAU_WEIGHT = 1.0  # Weight on plateau
