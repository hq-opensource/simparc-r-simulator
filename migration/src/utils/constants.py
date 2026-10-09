"""
Constants for geometry choices used in the migration helper functions.
"""
GEOMETRY_UNIT_DIRECTION_CHOICES = [
    "North",
    "North-Northeast",
    "Northeast",
    "East-Northeast",
    "East",
    "East-Southeast",
    "Southeast",
    "South-Southeast",
    "South",
    "South-Southwest",
    "Southwest",
    "West-Southwest",
    "West",
    "West-Northwest",
    "Northwest",
    "North-Northwest",
]

GEOMETRY_CEILING_HEIGHT_CHOICES = [
    f"{height:.1f} ft" for height in [x / 2 for x in range(12, 31)]
]