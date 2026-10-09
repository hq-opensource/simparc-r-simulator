"""Scalar formatters for legacy-to-v1.12 CSV migration.

Keep this module focused on one-value transformations such as rounding or
normalizing a single legacy field to a canonical option.
"""

import logging

from migration.src.utils.constants import (
    GEOMETRY_CEILING_HEIGHT_CHOICES,
    GEOMETRY_UNIT_DIRECTION_CHOICES,
)
from migration.src.utils.utils import _to_optional_float


logger = logging.getLogger(__name__)


def format_ceiling_height_choice(value):
    """Format the ceiling height value to the nearest half-foot choice."""
    ceiling_height = _to_optional_float(value)
    if ceiling_height is None:
        return None
    nearest_half_foot = round(ceiling_height * 2.0) / 2.0
    nearest_half_foot = max(6.0, min(15.0, nearest_half_foot))
    choice = f"{nearest_half_foot:.1f} ft"
    if choice not in GEOMETRY_CEILING_HEIGHT_CHOICES:
        logger.warning("No geometry_ceiling_height option found for value '%s'.", value)
        return None
    return choice


def format_unit_direction_choice(value):
    """Format the unit direction value to the nearest compass direction choice."""
    unit_direction = _to_optional_float(value)
    if unit_direction is None:
        return None

    normalized_degrees = unit_direction % 360.0
    choice_index = int((normalized_degrees / 22.5) + 0.5) % len(
        GEOMETRY_UNIT_DIRECTION_CHOICES
    )
    return GEOMETRY_UNIT_DIRECTION_CHOICES[choice_index]
