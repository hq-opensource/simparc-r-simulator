"""
Migrate old CSV files to the new format. from HPXML 4.1 to 5.0
This script is used to convert CSV files that were created with an older version of the simulator to the new format
that is compatible with the current version.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REPO_ROOT = SRC_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from migration.src.utils.constants import (  # noqa: E402
    GEOMETRY_CEILING_HEIGHT_CHOICES,
    GEOMETRY_UNIT_DIRECTION_CHOICES,
)
from migration.src.utils.migration_helper import (  # noqa: E402
    format_ceiling_height_choice,
    format_unit_direction_choice,
)
from migration.src.utils.read_option_tsv import (  # noqa: E402
    get_option_names,
    get_tsv_data,
)
from migration.src.utils.utils import (  # noqa: E402
    _build_geometry_unit_lookup,
    _build_misc_option_from_legacy,
    _legacy_overhang_cols,
    _match_enclosure_option,
    _log_approximation_warning_once,
    _match_option_by_numeric_properties,
    _normalize_duct_leakage_units,
    _normalize_legacy_value,
    _normalize_percent_value,
    _option_tsv_path,
    _to_bool,
    _to_float,
    _to_optional_float,
    _format_target_values_block,
    reset_approximation_warning_cache,
    _update_numeric_enclosure_option,
    _update_typed_numeric_enclosure_option,
    build_enclosure_air_leakage_value,
)


logger = logging.getLogger(__name__)


def update_column_values_v110_to_v112(df):
    """Replace "none" with "not present" in v1.10→v1.12 migration."""

    columns_to_update = [
        "wall_siding_type",
        "window_interior_shading_type",
        "window_exterior_shading_type",
        "pool_heater_type",
        "permanent_spa_heater_type",
    ]

    for column in columns_to_update:
        # Skip if column doesn't exist
        if column not in df.columns:
            continue
        # Update the specified column with the new value
        df[column] = df[column].replace("none", "not present")

    return df


def drop_legacy_columns(df, columns, message):
    """Drop legacy columns from the DataFrame if they exist, and log a message if any are dropped."""
    missing_columns = [column for column in columns if column not in df.columns]
    if len(missing_columns) != len(columns):
        logger.info(message)
    columns_to_drop = [column for column in columns if column in df.columns]
    if len(columns_to_drop) > 0:
        df.drop(columns=columns_to_drop, inplace=True)
    return df


def update_simulation_control_daylight_saving_enabled_v110_to_v112(df):
    """Drop the deprecated daylight-saving toggle; v1.12 derives DST from site defaults."""
    return drop_legacy_columns(
        df,
        ["simulation_control_daylight_saving_enabled"],
        "Dropping deprecated simulation_control_daylight_saving_enabled column.",
    )


def update_site_time_zone_utc_offset_v110_to_v112(df):
    """Drop the legacy site timezone offset; v1.12 resolves timezone from location defaults."""
    return drop_legacy_columns(
        df,
        ["site_time_zone_utc_offset"],
        "Dropping deprecated site_time_zone_utc_offset column.",
    )


def update_geometry_building_num_units_v110_to_v112(df):
    """Keep the legacy building-unit count input; v1.12 still writes it to HPXML."""
    if "geometry_building_num_units" in df.columns:
        logger.info("Keeping geometry_building_num_units for HPXML NumberofUnitsInBuilding.")
    return df


def update_year_built_v110_to_v112(df):
    """Rename the legacy year_built input to the v1.12 building_year_built field."""
    if "year_built" in df.columns:
        df.rename(columns={"year_built": "building_year_built"}, inplace=True)
    return df


def update_geometry_unit_cfa_v110_to_v112(df):
    """Rename the legacy unit floor area input to the v1.12 geometry_unit_conditioned_floor_area field."""
    if "geometry_unit_cfa" in df.columns:
        df.rename(
            columns={"geometry_unit_cfa": "geometry_unit_conditioned_floor_area"},
            inplace=True,
        )
    return df


def update_geometry_average_ceiling_height_v110_to_v112(df):
    """Map the legacy ceiling-height value to the v1.12 geometry_ceiling_height choice list."""
    if "geometry_average_ceiling_height" not in df.columns:
        return df

    df["geometry_ceiling_height"] = df["geometry_average_ceiling_height"].apply(
        format_ceiling_height_choice
    )
    df.drop(columns=["geometry_average_ceiling_height"], inplace=True)
    return df


def update_geometry_unit_orientation_v110_to_v112(df):
    """Map the legacy unit azimuth to the v1.12 geometry_unit_direction choice list."""
    if "geometry_unit_orientation" not in df.columns:
        return df

    df["geometry_unit_direction"] = df["geometry_unit_orientation"].apply(
        format_unit_direction_choice
    )
    df.drop(columns=["geometry_unit_orientation"], inplace=True)
    return df


def update_air_leakage_v110_to_v112(df):
    """
    Create the enclosure_air_leakage column from v1.10 air leakage component columns.

    Args:
        df (pd.DataFrame): The DataFrame to update.

    Returns:
        pd.DataFrame: The updated DataFrame with enclosure_air_leakage column.
    """
    reset_approximation_warning_cache()
    # Check if required columns exist
    required_cols = [
        "air_leakage_value",
        "air_leakage_units",
        "air_leakage_house_pressure",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        print(
            f"Warning: Missing columns {missing_cols}. Skipping enclosure_air_leakage creation."
        )
        return df

    new_air_leakage_values = []
    for idx, row in df.iterrows():
        value = row["air_leakage_value"]
        units = row["air_leakage_units"]
        pressure = row["air_leakage_house_pressure"]

        new_value = build_enclosure_air_leakage_value(value, units, pressure)
        new_air_leakage_values.append(new_value)

    # Normalize to canonical option names when available.
    tsv_path = _option_tsv_path("enclosure_air_leakage.tsv")
    option_names = get_option_names(str(tsv_path))

    # find closest match for each new value
    for i, new_value in enumerate(new_air_leakage_values):
        if new_value is None:
            continue
        canonical = _match_enclosure_option(new_value, option_names)
        if canonical is not None:
            new_air_leakage_values[i] = canonical
        else:
            logger.warning(
                f"No matching option found for enclosure_air_leakage value '{new_value}'. Setting to None."
            )
            new_air_leakage_values[i] = None
    df["enclosure_air_leakage"] = new_air_leakage_values

    # remove the old required_cols
    df.drop(columns=required_cols, inplace=True)

    return df

def update_geometry_unit_v110_to_v112(df):
    """
    Update the geometry_unit column from v1.10→v1.12 migration.

    Args:
        df (pd.DataFrame): The DataFrame to update.
    Returns:
        pd.DataFrame: The updated DataFrame.
    """
    tsv_path = _option_tsv_path("geometry_unit_type.tsv")
    geometry_unit_choices = _build_geometry_unit_lookup(str(tsv_path))
    option_names = get_option_names(str(tsv_path))
    option_names_lower = {name.lower(): name for name in option_names}

    aliases = {
        "singlefamilydetached": "singlefamilydetached",
        "singlefamilyattached": "singlefamilyattached",
        "apartment": "apartmentunit",
        "apartmentunit": "apartmentunit",
        "manufacturedhome": "manufacturedhome",
    }

    if (
        "geometry_unit_type" not in df.columns
        or "geometry_unit_num_floors_above_grade" not in df.columns
    ):
        print(
            "Warning: Missing column 'geometry_unit_type' or 'geometry_unit_num_floors_above_grade'. Skipping geometry_unit update."
        )
        return df

    for idx, row in df.iterrows():
        old_value_unit = str(row["geometry_unit_type"]).strip()
        old_value_floor = row["geometry_unit_num_floors_above_grade"]

        direct = option_names_lower.get(old_value_unit.lower())
        if direct is not None:
            df.at[idx, "geometry_unit_type"] = direct
            continue

        facility_key = aliases.get(
            _normalize_legacy_value(old_value_unit), _normalize_legacy_value(old_value_unit)
        )
        try:
            stories = int(float(str(old_value_floor).strip()))
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid geometry_unit_num_floors_above_grade '{old_value_floor}' for geometry_unit_type '{old_value_unit}'."
            )
            continue

        mapped = geometry_unit_choices.get((facility_key, stories))
        if mapped is None:
            logger.warning(
                f"No geometry unit option match for type '{old_value_unit}' and stories '{old_value_floor}'."
            )
            continue

        df.at[idx, "geometry_unit_type"] = mapped

    df.drop(columns=["geometry_unit_num_floors_above_grade"], inplace=True)

    return df

def update_geometry_attic_v110_to_v112(df):
    """Map legacy geometry_attic_type values to v1.12 option names."""
    reset_approximation_warning_cache()
    if ("geometry_attic_type" not in df.columns) or (
        "geometry_roof_type" not in df.columns
    ):
        print(
            "Warning: Missing column 'geometry_attic_type' or 'geometry_roof_type'. Skipping attic update."
        )
        return df

    tsv_path = _option_tsv_path("geometry_attic_type.tsv")
    rows = get_tsv_data(str(tsv_path))
    option_names = get_option_names(str(tsv_path))
    option_names_lower = {name.lower(): name for name in option_names}

    aliases = {
        "ventedattic": "VentedAttic",
        "unventedattic": "UnventedAttic",
        "conditionedattic": "ConditionedAttic",
        "flatroof": "FlatRoof",
        "belowapartment": "BelowApartment",
    }

    attic_lookup = {}
    by_attic_type = {}
    for row in rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue
        attic_type = str(row.get("Attic Type", "")).strip().lower()
        roof_type = str(row.get("Roof Type", "")).strip().lower()
        if attic_type == "":
            continue
        attic_lookup[(attic_type, roof_type)] = option_name
        by_attic_type.setdefault(attic_type, []).append(option_name)

    for idx, row in df.iterrows():
        old_attic = str(row["geometry_attic_type"]).strip()
        old_roof = str(row["geometry_roof_type"]).strip().lower()

        existing = option_names_lower.get(old_attic.lower())
        if existing is not None:
            df.at[idx, "geometry_attic_type"] = existing
            continue

        attic_key = aliases.get(_normalize_legacy_value(old_attic), _normalize_legacy_value(old_attic))
        attic_key = attic_key.lower()
        mapped = attic_lookup.get((attic_key, old_roof))
        approximate = False
        if mapped is None:
            candidates = by_attic_type.get(attic_key, [])
            if len(candidates) == 1:
                mapped = candidates[0]
                approximate = True
            elif len(candidates) > 1:
                gable = [c for c in candidates if "gable" in c.lower()]
                mapped = gable[0] if gable else candidates[0]
                approximate = True

        if mapped is None:
            logger.warning(
                f"No attic option match for geometry_attic_type '{old_attic}' and geometry_roof_type '{old_roof}'."
            )
            continue

        if approximate:
            _log_approximation_warning_once(
                ("geometry_attic_type", mapped),
                "Approximated geometry_attic_type '%s' and geometry_roof_type '%s' to '%s'.",
                old_attic,
                old_roof,
                mapped,
            )

        df.at[idx, "geometry_attic_type"] = mapped

    df.drop(columns=["geometry_roof_type"], inplace=True)

    return df

def update_geometry_foundation_v110_to_v112(df):
    """Map legacy geometry_foundation_type values to v1.12 option names."""
    reset_approximation_warning_cache()
    required_columns = [
        "geometry_foundation_type",
        "geometry_foundation_height_above_grade",
        "geometry_rim_joist_height",
        "geometry_foundation_height",
    ]

    if not all(col in df.columns for col in required_columns):
        print(
            "Warning: Missing one or more required columns for foundation update. Skipping foundation update."
        )
        return df

    tsv_path = _option_tsv_path("geometry_foundation_type.tsv")
    option_names = get_option_names(str(tsv_path))
    option_names_lower = {name.lower(): name for name in option_names}

    aliases = {
        "slabongrade": "Slab-on-Grade",
        "ventedcrawlspace": "Crawlspace, Vented",
        "unventedcrawlspace": "Crawlspace, Unvented",
        "conditionedcrawlspace": "Crawlspace, Conditioned",
        "unconditionedbasement": "Basement, Unconditioned",
        "conditionedbasement": "Basement, Conditioned",
        "ambient": "Ambient",
        "aboveapartment": "Above Apartment",
        "bellyandwingwithskirt": "Belly and Wing, With Skirt",
        "bellyandwingnoskirt": "Belly and Wing, No Skirt",
    }

    for idx, row in df.iterrows():
        old_value = row["geometry_foundation_type"]
        text = str(old_value).strip()

        direct = option_names_lower.get(text.lower())
        if direct is not None:
            df.at[idx, "geometry_foundation_type"] = direct
            continue

        legacy_key = _normalize_legacy_value(text)
        mapped = aliases.get(legacy_key)
        if mapped is None:
            logger.warning(
                f"No foundation option match for legacy geometry_foundation_type '{text}'."
            )
            continue

        hag = _to_float(row.get("geometry_foundation_height_above_grade"))
        if legacy_key in {"unconditionedbasement", "conditionedbasement"} and hag is not None and hag > 3.0:
            if "unconditioned" in mapped.lower():
                mapped = "Basement, Unconditioned, Half Above-Grade"
            elif "conditioned" in mapped.lower():
                mapped = "Basement, Conditioned, Half Above-Grade"
            _log_approximation_warning_once(
                ("geometry_foundation_type", mapped),
                "Approximated geometry_foundation_type '%s' with height above grade %s to '%s'.",
                text,
                hag,
                mapped,
            )
        elif legacy_key == "ventedcrawlspace" and hag is not None and hag > 3.0:
            mapped = "Detailed Example: Crawlspace, Vented, Above-Grade"
            _log_approximation_warning_once(
                ("geometry_foundation_type", mapped),
                "Approximated geometry_foundation_type '%s' with height above grade %s to '%s'.",
                text,
                hag,
                mapped,
            )

        df.at[idx, "geometry_foundation_type"] = mapped

    df.drop(columns=["geometry_foundation_height_above_grade"], inplace=True)
    df.drop(columns=["geometry_rim_joist_height"], inplace=True)
    df.drop(columns=["geometry_foundation_height"], inplace=True)

    return df


def update_enclosure_foundation_wall_v110_to_v112(df):
    """Map legacy foundation wall type and insulation fields to enclosure_foundation_wall."""
    reset_approximation_warning_cache()
    legacy_columns = [
        "foundation_wall_type",
        "foundation_wall_insulation_r",
        "foundation_wall_insulation_location",
        "foundation_wall_insulation_distance_to_top",
    ]
    if not any(column in df.columns for column in legacy_columns):
        return df

    tsv_path = _option_tsv_path("enclosure_foundation_wall.tsv")
    rows = get_tsv_data(str(tsv_path))
    option_names = get_option_names(str(tsv_path))
    option_names_lower = {name.lower(): name for name in option_names}

    valid_rows = []
    for row in rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue
        valid_rows.append(row)

    if "enclosure_foundation_wall" not in df.columns:
        df["enclosure_foundation_wall"] = None

    for idx, row in df.iterrows():
        current = str(row.get("enclosure_foundation_wall", "")).strip()
        if current != "":
            canonical = option_names_lower.get(current.lower())
            if canonical is not None:
                df.at[idx, "enclosure_foundation_wall"] = canonical
                continue

        legacy_type = str(row.get("foundation_wall_type", "")).strip()
        legacy_type_key = _normalize_legacy_value(legacy_type)
        legacy_location = str(row.get("foundation_wall_insulation_location", "")).strip()
        legacy_location_key = _normalize_legacy_value(legacy_location)
        legacy_r = _to_float(row.get("foundation_wall_insulation_r"))
        legacy_distance = _to_float(row.get("foundation_wall_insulation_distance_to_top"))

        candidate_rows = valid_rows
        if legacy_type_key != "":
            typed_rows = [
                opt
                for opt in valid_rows
                if _normalize_legacy_value(opt.get("Type")) == legacy_type_key
            ]
            if len(typed_rows) > 0:
                candidate_rows = typed_rows

        best_row = None
        best_score = None
        for opt in candidate_rows:
            score = 0.0
            compared = 0

            opt_type_key = _normalize_legacy_value(opt.get("Type"))
            if legacy_type_key != "":
                compared += 1
                if opt_type_key != legacy_type_key:
                    score += 1e6

            opt_location_key = _normalize_legacy_value(opt.get("Insulation Location"))
            if legacy_location_key != "":
                compared += 1
                if opt_location_key != legacy_location_key:
                    score += 10.0

            if legacy_r is not None:
                compared += 1
                opt_r = _to_float(opt.get("Insulation Nominal R-Value [F-ft2-hr/Btu]"))
                if opt_r is None:
                    score += 1e6
                else:
                    score += abs(opt_r - legacy_r)

            if legacy_distance is not None:
                compared += 1
                opt_distance = _to_float(opt.get("Insulation Distance To Top [ft]"))
                if opt_distance is None:
                    score += 1e6
                else:
                    score += abs(opt_distance - legacy_distance)

            if compared == 0:
                continue

            if best_score is None or score < best_score:
                best_score = score
                best_row = opt

        if best_row is None:
            logger.warning(
                "No enclosure_foundation_wall mapping found at row %s; using default 'Solid Concrete, Uninsulated'.",
                idx,
            )
            df.at[idx, "enclosure_foundation_wall"] = "Solid Concrete, Uninsulated"
            continue

        matched_name = str(best_row.get("Option Name", "")).strip()
        if best_score is not None and best_score > 1e-9:
            context_parts = []
            row_type = str(best_row.get("Type", "")).strip()
            if row_type != "":
                context_parts.append(row_type)
            row_r = _to_float(best_row.get("Insulation Nominal R-Value [F-ft2-hr/Btu]"))
            if row_r is not None:
                context_parts.append(str(row_r).rstrip("0").rstrip(".") if float(row_r).is_integer() is False else str(int(row_r)))
            row_location = str(best_row.get("Insulation Location", "")).strip()
            if row_location != "":
                context_parts.append(row_location)
            context = " ".join(context_parts)
            if context != "":
                context = f" : {context}"
            _log_approximation_warning_once(
                ("enclosure_foundation_wall", matched_name),
                "Approximated %s option using nearest match '%s'%s for target values %s.",
                tsv_path.name,
                matched_name,
                context,
                {
                    "Type": legacy_type,
                    "Insulation Nominal R-Value [F-ft2-hr/Btu]": legacy_r,
                    "Insulation Location": legacy_location,
                    "Insulation Distance To Top [ft]": legacy_distance,
                },
            )

        df.at[idx, "enclosure_foundation_wall"] = matched_name

    for column in legacy_columns:
        if column in df.columns:
            df.drop(columns=[column], inplace=True)

    return df


def update_enclosure_wall_v110_to_v112(df):
    """Map legacy wall type and assembly R-value to enclosure_wall."""
    reset_approximation_warning_cache()
    legacy_columns = {"wall_assembly_r": "Assembly R-Value [F-ft2-hr/Btu]"}
    df = _update_typed_numeric_enclosure_option(
        df,
        "wall_type",
        legacy_columns,
        "enclosure_wall.tsv",
        "enclosure_wall",
        "Wood Stud, R-13",
    )
    if "wall_type" in df.columns:
        df.drop(columns=["wall_type"], inplace=True)
    return drop_legacy_columns(
        df,
        list(legacy_columns.keys()),
        "Dropping legacy wall_assembly_r column after mapping to enclosure_wall.",
    )


def update_enclosure_ceiling_v110_to_v112(df):
    """Map legacy ceiling assembly R-value to enclosure_ceiling."""
    reset_approximation_warning_cache()
    legacy_columns = {"ceiling_assembly_r": "Assembly R-Value [F-ft2-hr/Btu]"}
    df = _update_numeric_enclosure_option(
        df,
        legacy_columns,
        "enclosure_ceiling.tsv",
        "enclosure_ceiling",
        "R-13",
    )
    return drop_legacy_columns(
        df,
        list(legacy_columns.keys()),
        "Dropping legacy ceiling_assembly_r column after mapping to enclosure_ceiling.",
    )


def update_enclosure_floor_over_foundation_v110_to_v112(df):
    """Map legacy floor-over-foundation assembly R-value to enclosure_floor_over_foundation."""
    reset_approximation_warning_cache()
    legacy_columns = {"floor_over_foundation_assembly_r": "Assembly R-Value [F-ft2-hr/Btu]"}
    df = _update_numeric_enclosure_option(
        df,
        legacy_columns,
        "enclosure_floor_over_foundation.tsv",
        "enclosure_floor_over_foundation",
        "Wood Frame, R-13",
    )
    return drop_legacy_columns(
        df,
        list(legacy_columns.keys()),
        "Dropping legacy floor_over_foundation_assembly_r column after mapping to enclosure_floor_over_foundation.",
    )


def update_enclosure_floor_over_garage_v110_to_v112(df):
    """Map legacy floor-over-garage assembly R-value to enclosure_floor_over_garage."""
    reset_approximation_warning_cache()
    legacy_columns = {"floor_over_garage_assembly_r": "Assembly R-Value [F-ft2-hr/Btu]"}
    df = _update_numeric_enclosure_option(
        df,
        legacy_columns,
        "enclosure_floor_over_garage.tsv",
        "enclosure_floor_over_garage",
        "Wood Frame, R-13",
    )
    return drop_legacy_columns(
        df,
        list(legacy_columns.keys()),
        "Dropping legacy floor_over_garage_assembly_r column after mapping to enclosure_floor_over_garage.",
    )


def _map_enclosure_slab_option(tsv_rows, perimeter_r, under_r):
    """Map legacy slab insulation values to the closest v1.12 enclosure_slab option."""
    perimeter_r = 0 if perimeter_r is None else perimeter_r
    under_r = 0 if under_r is None else under_r

    if perimeter_r <= 0 and under_r <= 0:
        return "Uninsulated"

    if perimeter_r > 0 and under_r > 0:
        if abs(perimeter_r - under_r) <= 1e-9:
            target_values = {
                "Under Slab Insulation Nominal R-Value [F-ft2-hr/Btu]": under_r,
                "Under Slab Insulation Width [ft]": 999,
            }
        elif under_r > perimeter_r:
            target_values = {
                "Under Slab Insulation Nominal R-Value [F-ft2-hr/Btu]": under_r,
                "Under Slab Insulation Width [ft]": 2,
            }
        else:
            target_values = {
                "Perimeter Insulation Nominal R-Value [F-ft2-hr/Btu]": perimeter_r,
                "Perimeter Insulation Depth [ft]": 2,
            }
    elif under_r > 0:
        target_values = {
            "Under Slab Insulation Nominal R-Value [F-ft2-hr/Btu]": under_r,
            "Under Slab Insulation Width [ft]": 2,
        }
    else:
        target_values = {
            "Perimeter Insulation Nominal R-Value [F-ft2-hr/Btu]": perimeter_r,
            "Perimeter Insulation Depth [ft]": 2,
        }

    return _match_option_by_numeric_properties(
        _option_tsv_path("enclosure_slab.tsv"),
        target_values,
        rows=tsv_rows,
    )


def update_enclosure_slab_v110_to_v112(df):
    """Map legacy floor_type and slab insulation values to enclosure_slab."""
    reset_approximation_warning_cache()

    legacy_columns = ["floor_type", "slab_perimeter_insulation_r", "slab_under_insulation_r"]
    if not any(column in df.columns for column in legacy_columns):
        return df

    tsv_rows = get_tsv_data(str(_option_tsv_path("enclosure_slab.tsv")))

    if "floor_type" in df.columns:
        non_default_floor_types = sorted(
            {
                str(value).strip()
                for value in df["floor_type"].dropna().unique().tolist()
                if str(value).strip() != "" and str(value).strip() != "WoodFrame"
            }
        )
        if len(non_default_floor_types) > 0:
            _log_approximation_warning_once(
                ("floor_type", tuple(non_default_floor_types)),
                "Dropping legacy floor_type values with no v1.12 enclosure_slab equivalent: %s",
                ", ".join(non_default_floor_types),
            )

    for idx, row in df.iterrows():
        perimeter_r = _to_float(row.get("slab_perimeter_insulation_r"))
        under_r = _to_float(row.get("slab_under_insulation_r"))

        matched_name = _map_enclosure_slab_option(tsv_rows, perimeter_r, under_r)
        if matched_name is None:
            matched_name = "Uninsulated"
            _log_approximation_warning_once(
                ("enclosure_slab", matched_name),
                "No enclosure_slab mapping found at row %s; using default '%s'.",
                idx,
                matched_name,
            )

        df.at[idx, "enclosure_slab"] = matched_name

    return drop_legacy_columns(
        df,
        legacy_columns,
        "Dropping legacy floor_type, slab_perimeter_insulation_r and slab_under_insulation_r columns after mapping to enclosure_slab.",
    )


def update_enclosure_window_v110_to_v112(df):
    """Map legacy window U-factor and SHGC columns to enclosure_window."""
    legacy_columns = {
        "window_ufactor": "U-Factor [Btu/hr-ft2-F]",
        "window_shgc": "SHGC",
    }
    df = _update_numeric_enclosure_option(
        df,
        legacy_columns,
        "enclosure_window.tsv",
        "enclosure_window",
        "Double, Clear, Metal, Air",
    )
    return drop_legacy_columns(
        df,
        list(legacy_columns.keys()),
        "Dropping legacy window_ufactor and window_shgc columns.",
    )


def update_enclosure_skylight_v110_to_v112(df):
    """Map legacy skylight U-factor and SHGC columns to enclosure_skylight."""
    legacy_columns = {
        "skylight_ufactor": "U-Factor [Btu/hr-ft2-F]",
        "skylight_shgc": "SHGC",
    }
    df = _update_numeric_enclosure_option(
        df,
        legacy_columns,
        "enclosure_skylight.tsv",
        "enclosure_skylight",
        "Single, Clear, Metal",
    )
    return drop_legacy_columns(
        df,
        list(legacy_columns.keys()),
        "Dropping legacy skylight_ufactor and skylight_shgc columns.",
    )


def update_window_interior_shading_v110_to_v112(df):
    """Map legacy window interior shading coefficients to enclosure_window_interior_shading."""
    legacy_columns = {
        "window_interior_shading_summer": "Summer Coefficient [frac]",
        "window_interior_shading_winter": "Winter Coefficient [frac]",
    }
    df = _update_numeric_enclosure_option(
        df,
        legacy_columns,
        "enclosure_window_interior_shading.tsv",
        "enclosure_window_interior_shading",
        "Curtains, Light",
    )
    return drop_legacy_columns(
        df,
        list(legacy_columns.keys()),
        "Dropping legacy window_interior_shading_summer and window_interior_shading_winter columns.",
    )


def _format_geometry_numeric_value(value, default):
    numeric_value = _to_optional_float(value)
    if numeric_value is None:
        numeric_value = default
    return format(numeric_value, "g")


def update_geometry_window_areas_or_wwrs_v110_to_v112(df):
    """Map legacy facade window WWR/area columns to geometry_window_areas_or_wwrs."""
    legacy_columns = [
        "window_front_wwr",
        "window_back_wwr",
        "window_left_wwr",
        "window_right_wwr",
        "window_area_front",
        "window_area_back",
        "window_area_left",
        "window_area_right",
        "window_aspect_ratio",
    ]
    if not any(column in df.columns for column in legacy_columns):
        return df

    if "geometry_window_areas_or_wwrs" not in df.columns:
        df["geometry_window_areas_or_wwrs"] = None

    if "window_aspect_ratio" in df.columns:
        non_default_aspect_ratios = sorted(
            {
                str(value).strip()
                for value in df["window_aspect_ratio"].dropna().unique().tolist()
                if str(value).strip() not in {"", "1.333"}
            }
        )
        if len(non_default_aspect_ratios) > 0:
            _log_approximation_warning_once(
                ("window_aspect_ratio", tuple(non_default_aspect_ratios)),
                "Dropping legacy window_aspect_ratio values with no v1.12 equivalent: %s",
                ", ".join(non_default_aspect_ratios),
            )

    wwr_columns = ["window_front_wwr", "window_back_wwr", "window_left_wwr", "window_right_wwr"]
    area_columns = ["window_area_front", "window_area_back", "window_area_left", "window_area_right"]

    for idx, row in df.iterrows():
        current_value = str(df.at[idx, "geometry_window_areas_or_wwrs"]).strip()
        if current_value.lower() not in {"", "none", "nan"}:
            continue

        wwr_values = [_to_optional_float(row.get(column)) for column in wwr_columns]
        area_values = [_to_optional_float(row.get(column)) for column in area_columns]
        has_nonzero_wwr = any(value is not None and abs(value) > 1e-9 for value in wwr_values)
        has_nonzero_area = any(value is not None and abs(value) > 1e-9 for value in area_values)

        if has_nonzero_area and not has_nonzero_wwr:
            values = area_values
            default_value = 0.0
        else:
            values = wwr_values
            default_value = 0.15

        df.at[idx, "geometry_window_areas_or_wwrs"] = ", ".join(
            _format_geometry_numeric_value(value, default_value) for value in values
        )

    return drop_legacy_columns(
        df,
        legacy_columns,
        "Dropping legacy window WWR, area and aspect ratio columns after mapping to geometry_window_areas_or_wwrs.",
    )


def update_geometry_skylight_areas_v110_to_v112(df):
    """Map legacy skylight area columns to geometry_skylight_areas."""
    legacy_columns = [
        "skylight_area_front",
        "skylight_area_back",
        "skylight_area_left",
        "skylight_area_right",
    ]
    if not any(column in df.columns for column in legacy_columns):
        return df

    if "geometry_skylight_areas" not in df.columns:
        df["geometry_skylight_areas"] = None

    skylight_columns = ["skylight_area_front", "skylight_area_back", "skylight_area_left", "skylight_area_right"]

    for idx, row in df.iterrows():
        current_value = str(df.at[idx, "geometry_skylight_areas"]).strip()
        if current_value.lower() not in {"", "none", "nan"}:
            continue

        values = [_to_optional_float(row.get(column)) for column in skylight_columns]
        df.at[idx, "geometry_skylight_areas"] = ", ".join(
            _format_geometry_numeric_value(value, 0.0) for value in values
        )

    return drop_legacy_columns(
        df,
        legacy_columns,
        "Dropping legacy skylight area columns after mapping to geometry_skylight_areas.",
    )

def update_enclosure_overhangs_v110_to_v112(df):
    """Map legacy detailed overhang columns to the v1.12 enclosure_overhangs option."""
    reset_approximation_warning_cache()

    tsv_path = _option_tsv_path("enclosure_overhangs.tsv")
    rows = get_tsv_data(str(tsv_path))
    option_names = get_option_names(str(tsv_path))
    option_names_lower = {name.lower(): name for name in option_names}

    # Keep only actual options (skip comments/empty rows).
    option_rows = []
    for row in rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue
        option_rows.append(row)

    if "enclosure_overhangs" not in df.columns:
        df["enclosure_overhangs"] = None

    legacy_sets = [_legacy_overhang_cols(""), _legacy_overhang_cols("geometry_")]

    for idx, row in df.iterrows():
        existing = str(row.get("enclosure_overhangs", "")).strip()
        if existing != "":
            canonical = option_names_lower.get(existing.lower())
            if canonical is not None:
                df.at[idx, "enclosure_overhangs"] = canonical
                continue

        # Choose legacy namespace (plain or geometry_) with the most populated values.
        selected = None
        selected_count = -1
        for colset in legacy_sets:
            count = 0
            for col in colset.values():
                if col in df.columns and _to_float(row.get(col)) is not None:
                    count += 1
            if count > selected_count:
                selected = colset
                selected_count = count

        if selected is None or selected_count == 0:
            df.at[idx, "enclosure_overhangs"] = "None"
            continue

        depths = {
            "Front Depth [ft]": _to_float(row.get(selected["front_depth"])),
            "Back Depth [ft]": _to_float(row.get(selected["back_depth"])),
            "Left Depth [ft]": _to_float(row.get(selected["left_depth"])),
            "Right Depth [ft]": _to_float(row.get(selected["right_depth"])),
        }

        top_values = []
        for key in ["front_top", "back_top", "left_top", "right_top"]:
            col = selected[key]
            if col in df.columns:
                val = _to_float(row.get(col))
                if val is not None:
                    top_values.append(val)

        bottom_values = []
        for key in ["front_bottom", "back_bottom", "left_bottom", "right_bottom"]:
            col = selected[key]
            if col in df.columns:
                val = _to_float(row.get(col))
                if val is not None:
                    bottom_values.append(val)

        top = top_values[0] if len(top_values) > 0 else None
        bottom = bottom_values[0] if len(bottom_values) > 0 else None

        if len(top_values) > 1 and len(set(top_values)) > 1:
            logger.warning(
                f"Overhang top offsets differ by facade at row {idx}; using first value ({top})."
            )
        if len(bottom_values) > 1 and len(set(bottom_values)) > 1:
            logger.warning(
                f"Overhang bottom offsets differ by facade at row {idx}; using first value ({bottom})."
            )

        depth_values = [d for d in depths.values() if d is not None]
        if len(depth_values) == 0 or all(abs(d) < 1e-9 for d in depth_values):
            df.at[idx, "enclosure_overhangs"] = "None"
            continue

        target = dict(depths)
        target["Distance to Top of Window [ft]"] = top
        target["Distance to Bottom of Window [ft]"] = bottom

        # Exact match first.
        matched_name = None
        for opt in option_rows:
            ok = True
            for key, value in target.items():
                if value is None:
                    continue
                opt_value = _to_float(opt.get(key))
                if opt_value is None or abs(opt_value - value) > 1e-6:
                    ok = False
                    break
            if ok:
                matched_name = str(opt.get("Option Name", "")).strip()
                break

        # Nearest fallback if no exact option exists.
        if matched_name is None:
            best_name = None
            best_score = None
            for opt in option_rows:
                score = 0.0
                compared = 0
                for key, value in target.items():
                    if value is None:
                        continue
                    opt_value = _to_float(opt.get(key))
                    if opt_value is None:
                        score += 1e6
                    else:
                        score += abs(opt_value - value)
                    compared += 1
                if compared == 0:
                    continue
                if best_score is None or score < best_score:
                    best_score = score
                    best_name = str(opt.get("Option Name", "")).strip()

            if best_name is not None:
                matched_name = best_name
                _log_approximation_warning_once(
                    (
                        matched_name,
                    ),
                    "Using nearest enclosure_overhangs option '%s' at row %s.",
                    matched_name,
                    idx,
                )

        if matched_name is None:
            logger.warning(
                f"No enclosure_overhangs mapping found at row {idx}; setting to 'None'."
            )
            matched_name = "None"

        canonical = option_names_lower.get(matched_name.lower(), matched_name)
        df.at[idx, "enclosure_overhangs"] = canonical

    legacy_cols = set()
    for colset in legacy_sets:
        legacy_cols.update(colset.values())
    cols_to_drop = [col for col in legacy_cols if col in df.columns]
    if len(cols_to_drop) > 0:
        df.drop(columns=cols_to_drop, inplace=True)

    return df

def update_pool_parameters_v110_to_v112(df):
    """Map legacy pool/spa columns to v1.12 misc_pool/misc_permanent_spa option names."""
    pool_tsv_path = _option_tsv_path("misc_pool.tsv")
    spa_tsv_path = _option_tsv_path("misc_permanent_spa.tsv")

    pool_rows = get_tsv_data(str(pool_tsv_path))
    spa_rows = get_tsv_data(str(spa_tsv_path))
    pool_option_names = get_option_names(str(pool_tsv_path))
    spa_option_names = get_option_names(str(spa_tsv_path))
    pool_option_names_lower = {name.lower(): name for name in pool_option_names}
    spa_option_names_lower = {name.lower(): name for name in spa_option_names}

    if "misc_pool" not in df.columns:
        df["misc_pool"] = None
    if "misc_permanent_spa" not in df.columns:
        df["misc_permanent_spa"] = None

    for idx, row in df.iterrows():
        # Keep already valid v1.12 option as-is.
        current_pool = str(row.get("misc_pool", "")).strip()
        if current_pool != "" and current_pool.lower() in pool_option_names_lower:
            df.at[idx, "misc_pool"] = pool_option_names_lower[current_pool.lower()]
        else:
            df.at[idx, "misc_pool"] = _build_misc_option_from_legacy(
                row=row,
                present_col="pool_present",
                pump_annual_col="pool_pump_annual_kwh",
                pump_multiplier_col="pool_pump_usage_multiplier",
                heater_type_col="pool_heater_type",
                heater_annual_kwh_col="pool_heater_annual_kwh",
                heater_annual_therm_col="pool_heater_annual_therm",
                heater_multiplier_col="pool_heater_usage_multiplier",
                tsv_rows=pool_rows,
            )

        current_spa = str(row.get("misc_permanent_spa", "")).strip()
        if current_spa != "" and current_spa.lower() in spa_option_names_lower:
            df.at[idx, "misc_permanent_spa"] = spa_option_names_lower[current_spa.lower()]
        else:
            df.at[idx, "misc_permanent_spa"] = _build_misc_option_from_legacy(
                row=row,
                present_col="permanent_spa_present",
                pump_annual_col="permanent_spa_pump_annual_kwh",
                pump_multiplier_col="permanent_spa_pump_usage_multiplier",
                heater_type_col="permanent_spa_heater_type",
                heater_annual_kwh_col="permanent_spa_heater_annual_kwh",
                heater_annual_therm_col="permanent_spa_heater_annual_therm",
                heater_multiplier_col="permanent_spa_heater_usage_multiplier",
                tsv_rows=spa_rows,
            )

    old_columns = [
        "pool_present",
        "pool_pump_annual_kwh",
        "pool_pump_usage_multiplier",
        "pool_heater_type",
        "pool_heater_annual_kwh",
        "pool_heater_annual_therm",
        "pool_heater_usage_multiplier",
        "permanent_spa_present",
        "permanent_spa_pump_annual_kwh",
        "permanent_spa_pump_usage_multiplier",
        "permanent_spa_heater_type",
        "permanent_spa_heater_annual_kwh",
        "permanent_spa_heater_annual_therm",
        "permanent_spa_heater_usage_multiplier",
    ]
    cols_to_drop = [c for c in old_columns if c in df.columns]
    if len(cols_to_drop) > 0:
        df.drop(columns=cols_to_drop, inplace=True)

    return df


def _map_dhw_water_heater_option(tsv_rows, row):
    """Map legacy water heater fields to the closest v1.12 dhw_water_heater option."""
    legacy_type = _normalize_legacy_value(row.get("water_heater_type"))
    legacy_fuel = _normalize_legacy_value(row.get("water_heater_fuel_type"))
    legacy_efficiency_type = _normalize_legacy_value(row.get("water_heater_efficiency_type"))
    legacy_efficiency = _to_float(row.get("water_heater_efficiency"))
    legacy_recovery = _to_optional_float(row.get("water_heater_recovery_efficiency"))
    legacy_temperature = _to_optional_float(row.get("water_heater_setpoint_temperature"))

    best_name = None
    best_score = None
    for candidate in tsv_rows:
        option_name = str(candidate.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue

        candidate_type = _normalize_legacy_value(candidate.get("Type"))
        candidate_fuel = _normalize_legacy_value(candidate.get("Fuel Type"))
        candidate_efficiency_type = _normalize_legacy_value(candidate.get("Efficiency Type"))

        if legacy_type != "" and candidate_type != legacy_type:
            continue
        if legacy_fuel != "" and candidate_fuel != legacy_fuel:
            continue

        score = 0.0
        if legacy_efficiency is not None:
            candidate_efficiency = _to_optional_float(candidate.get("Efficiency [frac]"))
            if candidate_efficiency is None:
                score += 1e6
            else:
                score += abs(candidate_efficiency - legacy_efficiency)

        if legacy_recovery is not None:
            candidate_recovery = _to_optional_float(candidate.get("Recovery Efficiency [frac]"))
            if candidate_recovery is not None:
                score += abs(candidate_recovery - legacy_recovery) * 0.1

        if legacy_temperature is not None:
            candidate_temperature = _to_optional_float(candidate.get("Temperature [F]"))
            if candidate_temperature is not None:
                score += abs(candidate_temperature - legacy_temperature) * 0.01

        if legacy_efficiency_type != "" and candidate_efficiency_type != "":
            if candidate_efficiency_type != legacy_efficiency_type:
                score += 0.001

        if best_score is None or score < best_score:
            best_score = score
            best_name = option_name

    if best_name is None:
        return None

    if best_score is not None and best_score > 1e-9:
        _log_approximation_warning_once(
            ("dhw_water_heater", best_name),
            "Approximated dhw_water_heater option using nearest match '%s'\n  target values:\n%s",
            best_name,
            _format_target_values_block(
                {
                    "water_heater_type": row.get("water_heater_type", ""),
                    "water_heater_fuel_type": row.get("water_heater_fuel_type", ""),
                    "water_heater_efficiency_type": row.get("water_heater_efficiency_type", ""),
                    "water_heater_efficiency": row.get("water_heater_efficiency", ""),
                    "water_heater_recovery_efficiency": row.get("water_heater_recovery_efficiency", ""),
                    "water_heater_setpoint_temperature": row.get("water_heater_setpoint_temperature", ""),
                }
            ),
        )

    return best_name


def update_dhw_water_heater_v110_to_v112(df):
    """Map legacy water-heater columns to dhw_water_heater and dhw_water_heater_location."""
    reset_approximation_warning_cache()

    legacy_columns = [
        "water_heater_fuel_type",
        "water_heater_efficiency_type",
        "water_heater_efficiency",
        "water_heater_recovery_efficiency",
        "water_heater_standby_loss",
        "water_heater_jacket_rvalue",
        "water_heater_setpoint_temperature",
        "water_heater_type",
        "water_heater_location",
    ]
    if not any(column in df.columns for column in legacy_columns):
        return df

    tsv_rows = get_tsv_data(str(_option_tsv_path("dhw_water_heater.tsv")))
    option_names = get_option_names(str(_option_tsv_path("dhw_water_heater.tsv")))
    option_names_lower = {name.lower(): name for name in option_names}
    location_lookup = {
        "conditionedspace": "Conditioned Space",
        "othermultifamilybufferspace": "SFA/MF Other Heated Space",
        "basement": "Basement",
        "garage": "Garage",
        "crawlspace": "Crawlspace",
        "attic": "Attic",
        "sfamfotherheatedspace": "SFA/MF Other Heated Space",
        "default": "Default",
    }

    if "dhw_water_heater" not in df.columns:
        df["dhw_water_heater"] = None
    if "dhw_water_heater_location" not in df.columns:
        df["dhw_water_heater_location"] = None

    for idx, row in df.iterrows():
        current = str(row.get("dhw_water_heater", "")).strip()
        if current != "" and current.lower() in option_names_lower:
            df.at[idx, "dhw_water_heater"] = option_names_lower[current.lower()]
        else:
            matched = _map_dhw_water_heater_option(tsv_rows, row)
            if matched is None:
                df.at[idx, "dhw_water_heater"] = "None"
                _log_approximation_warning_once(
                    ("dhw_water_heater", "None"),
                    "No dhw_water_heater mapping found at row %s; using default 'None'.",
                    idx,
                )
            else:
                df.at[idx, "dhw_water_heater"] = matched

        legacy_location = _normalize_legacy_value(row.get("water_heater_location"))
        df.at[idx, "dhw_water_heater_location"] = location_lookup.get(
            legacy_location,
            location_lookup.get("default"),
        )

    return drop_legacy_columns(
        df,
        legacy_columns,
        "Dropping legacy water_heater_* columns after mapping to dhw_water_heater and dhw_water_heater_location.",
    )


def _ventilation_mechanical_target_values(row):
    return {
        "fan_type": _normalize_legacy_value(row.get("mech_vent_fan_type")),
        "sensible_efficiency": _to_optional_float(row.get("mech_vent_sensible_recovery_efficiency")),
        "total_efficiency": _to_optional_float(row.get("mech_vent_total_recovery_efficiency")),
    }


def _match_ventilation_mechanical_option(tsv_rows, target):
    fan_type = target["fan_type"]
    sensible_efficiency = target["sensible_efficiency"]
    total_efficiency = target["total_efficiency"]

    if fan_type in {"", "none"}:
        return "None"

    best_name = None
    best_score = None
    for row in tsv_rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue

        candidate_fan_type = _normalize_legacy_value(row.get("Fan Type"))
        if candidate_fan_type != fan_type:
            continue

        score = 0.0
        compared = 0

        if sensible_efficiency is not None:
            candidate_sensible = _to_optional_float(row.get("Sensible Recovery Efficiency [frac]"))
            if candidate_sensible is None:
                score += 1e6
            else:
                score += abs(candidate_sensible - sensible_efficiency)
            compared += 1

        if total_efficiency is not None:
            candidate_total = _to_optional_float(row.get("Total Recovery Efficiency [frac]"))
            if candidate_total is not None:
                score += abs(candidate_total - total_efficiency)
            else:
                score += 1e-9
            compared += 1

        if compared == 0:
            continue

        if best_score is None or score < best_score:
            best_score = score
            best_name = option_name

    if best_name is None:
        return None

    if best_score is not None and best_score > 1e-9:
        _log_approximation_warning_once(
            ("ventilation_mechanical", best_name),
            "Approximated ventilation_mechanical option using nearest match '%s'\n  target values:\n%s",
            best_name,
            _format_target_values_block(
                {
                    "mech_vent_fan_type": fan_type,
                    "mech_vent_sensible_recovery_efficiency": sensible_efficiency,
                    "mech_vent_total_recovery_efficiency": total_efficiency,
                }
            ),
        )

    return best_name


def _update_ventilation_mechanical_column(df, idx, row, existing_mech, mech_option_names_lower, mech_tsv_rows):
    current_mech = str(existing_mech.iloc[idx]).strip() if existing_mech is not None else ""
    if current_mech not in {"", "none", "nan"} and current_mech.lower() in mech_option_names_lower:
        df.at[idx, "ventilation_mechanical"] = mech_option_names_lower[current_mech.lower()]
        return

    matched = _match_ventilation_mechanical_option(
        mech_tsv_rows,
        _ventilation_mechanical_target_values(row),
    )
    if matched is None:
        matched = "None"
        _log_approximation_warning_once(
            ("ventilation_mechanical", matched),
            "No ventilation_mechanical mapping found at row %s; using default '%s'.",
            idx,
            matched,
        )
    df.at[idx, "ventilation_mechanical"] = matched


def _update_ventilation_kitchen_column(df, idx, row, existing_kitchen):
    current_kitchen = str(existing_kitchen.iloc[idx]).strip() if existing_kitchen is not None else ""
    if current_kitchen not in {"", "none", "nan"}:
        df.at[idx, "ventilation_kitchen"] = current_kitchen
        return

    if row.get("kitchen_fans_start_hour") not in {None, ""}:
        df.at[idx, "ventilation_kitchen"] = "Default"
        kitchen_start_hour = row.get("kitchen_fans_start_hour")
        _log_approximation_warning_once(
            ("ventilation_kitchen", "Default", kitchen_start_hour),
            "Legacy kitchen fan timing has no direct v1.12 option-string equivalent for kitchen_fans_start_hour=%s; using Default.",
            kitchen_start_hour,
        )
        return

    df.at[idx, "ventilation_kitchen"] = "None"


def _update_ventilation_bathroom_column(df, idx, row, existing_bathroom):
    current_bathroom = str(existing_bathroom.iloc[idx]).strip() if existing_bathroom is not None else ""
    if current_bathroom not in {"", "none", "nan"}:
        df.at[idx, "ventilation_bathroom"] = current_bathroom
        return

    if row.get("bathroom_fans_start_hour") not in {None, ""}:
        df.at[idx, "ventilation_bathroom"] = "Default"
        bathroom_start_hour = row.get("bathroom_fans_start_hour")
        _log_approximation_warning_once(
            ("ventilation_bathroom", "Default", bathroom_start_hour),
            "Legacy bathroom fan timing has no direct v1.12 option-string equivalent for bathroom_fans_start_hour=%s; using Default.",
            bathroom_start_hour,
        )
        return

    df.at[idx, "ventilation_bathroom"] = "None"


def _update_ventilation_whole_house_fan_column(df, idx, row, existing_whole_house, whole_house_option_names_lower, whole_house_tsv_path, whole_house_rows):
    current_whole_house = str(existing_whole_house.iloc[idx]).strip() if existing_whole_house is not None else ""
    if current_whole_house not in {"", "none", "nan"} and current_whole_house.lower() in whole_house_option_names_lower:
        df.at[idx, "ventilation_whole_house_fan"] = whole_house_option_names_lower[current_whole_house.lower()]
        return

    present = str(row.get("whole_house_fan_present", "")).strip().lower()
    flow_rate = _to_float(row.get("whole_house_fan_flow_rate"))
    fan_power = _to_float(row.get("whole_house_fan_power"))
    if present in {"false", "0", "no", "n"} or (flow_rate is not None and abs(flow_rate) < 1e-9 and (fan_power is None or abs(fan_power) < 1e-9)):
        df.at[idx, "ventilation_whole_house_fan"] = "None"
        return

    matched = _match_option_by_numeric_properties(
        str(whole_house_tsv_path),
        {
            "Rated Flow Rate [cfm]": flow_rate,
            "Power [W]": fan_power,
        },
        rows=whole_house_rows,
    )
    if matched is None:
        matched = "None"
    df.at[idx, "ventilation_whole_house_fan"] = matched


def _update_ventilation_window_natural_column(df, idx, row, existing_window_natvent, window_natvent_option_names_lower, window_natvent_tsv_path, window_natvent_rows):
    current_natvent = str(existing_window_natvent.iloc[idx]).strip() if existing_window_natvent is not None else ""
    if current_natvent not in {"", "none", "nan"} and current_natvent.lower() in window_natvent_option_names_lower:
        df.at[idx, "enclosure_window_natural_ventilation"] = window_natvent_option_names_lower[current_natvent.lower()]
        return

    fraction_operable = _to_float(row.get("window_fraction_operable"))
    if fraction_operable is None:
        df.at[idx, "enclosure_window_natural_ventilation"] = "None"
        return

    matched = _match_option_by_numeric_properties(
        str(window_natvent_tsv_path),
        {"Fraction Operable [frac]": fraction_operable},
        rows=window_natvent_rows,
    )
    if matched is None:
        matched = "None"
    df.at[idx, "enclosure_window_natural_ventilation"] = matched


def update_ventilation_v110_to_v112(df):
    """Map legacy ventilation columns to the v1.12 ventilation option strings."""
    reset_approximation_warning_cache()

    mech_cols = [
        "mech_vent_fan_type",
        "mech_vent_flow_rate",
        "mech_vent_hours_in_operation",
        "mech_vent_recovery_efficiency_type",
        "mech_vent_total_recovery_efficiency",
        "mech_vent_sensible_recovery_efficiency",
        "mech_vent_fan_power",
        "mech_vent_num_units_served",
        "whole_house_fan_present",
        "whole_house_fan_flow_rate",
        "whole_house_fan_power",
        "bathroom_fans_start_hour",
        "kitchen_fans_start_hour",
        "window_fraction_operable",
    ]
    if not any(column in df.columns for column in mech_cols):
        return df

    mech_tsv_rows = get_tsv_data(str(_option_tsv_path("ventilation_mechanical.tsv")))
    mech_option_names = get_option_names(str(_option_tsv_path("ventilation_mechanical.tsv")))
    mech_option_names_lower = {name.lower(): name for name in mech_option_names}

    whole_house_tsv_path = _option_tsv_path("ventilation_whole_house_fan.tsv")
    whole_house_rows = get_tsv_data(str(whole_house_tsv_path))
    whole_house_option_names = get_option_names(str(whole_house_tsv_path))
    whole_house_option_names_lower = {name.lower(): name for name in whole_house_option_names}

    window_natvent_tsv_path = _option_tsv_path("enclosure_window_natural_ventilation.tsv")
    window_natvent_rows = get_tsv_data(str(window_natvent_tsv_path))
    window_natvent_option_names = get_option_names(str(window_natvent_tsv_path))
    window_natvent_option_names_lower = {name.lower(): name for name in window_natvent_option_names}

    if "ventilation_mechanical" in df.columns:
        existing_mech = df["ventilation_mechanical"]
    else:
        existing_mech = None

    if "ventilation_kitchen" in df.columns:
        existing_kitchen = df["ventilation_kitchen"]
    else:
        existing_kitchen = None

    if "ventilation_bathroom" in df.columns:
        existing_bathroom = df["ventilation_bathroom"]
    else:
        existing_bathroom = None

    if "ventilation_whole_house_fan" in df.columns:
        existing_whole_house = df["ventilation_whole_house_fan"]
    else:
        existing_whole_house = None

    if "enclosure_window_natural_ventilation" in df.columns:
        existing_window_natvent = df["enclosure_window_natural_ventilation"]
    else:
        existing_window_natvent = None

    for idx, row in df.iterrows():
        _update_ventilation_mechanical_column(df, idx, row, existing_mech, mech_option_names_lower, mech_tsv_rows)
        _update_ventilation_kitchen_column(df, idx, row, existing_kitchen)
        _update_ventilation_bathroom_column(df, idx, row, existing_bathroom)
        _update_ventilation_whole_house_fan_column(
            df,
            idx,
            row,
            existing_whole_house,
            whole_house_option_names_lower,
            whole_house_tsv_path,
            whole_house_rows,
        )
        _update_ventilation_window_natural_column(
            df,
            idx,
            row,
            existing_window_natvent,
            window_natvent_option_names_lower,
            window_natvent_tsv_path,
            window_natvent_rows,
        )

    return drop_legacy_columns(
        df,
        mech_cols,
        "Dropping legacy ventilation columns after mapping to v1.12 ventilation options.",
    )

def _match_choice_option_by_tsv_properties(tsv_rows, target_values, context_label, field_weights=None):
    best_name = None
    best_row = None
    best_score = None
    field_weights = field_weights or {}

    for row in tsv_rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue

        score = 0.0
        compared = 0
        for tsv_key, target_value in target_values.items():
            if target_value is None:
                continue
            if isinstance(target_value, str) and target_value.strip() == "":
                continue

            weight = float(field_weights.get(tsv_key, 1.0))
            if weight <= 0:
                continue

            compared += 1
            candidate_value = row.get(tsv_key)
            candidate_text = "" if candidate_value is None else str(candidate_value).strip()
            target_text = str(target_value).strip()

            candidate_float = _to_optional_float(candidate_value)
            target_float = _to_optional_float(target_value)
            if candidate_float is not None and target_float is not None:
                score += weight * abs(candidate_float - target_float)
                continue

            if target_float is not None and candidate_float is None:
                score += weight * 100.0
                continue

            if _normalize_legacy_value(candidate_text) != _normalize_legacy_value(target_text):
                score += weight

        if compared == 0:
            continue

        if best_score is None or score < best_score:
            best_score = score
            best_name = option_name
            best_row = row

    if best_name is None:
        return None

    if best_score is not None and best_score > 1e-9:
        context_label_name = None
        context_value_text = None
        if best_row is not None:
            preferred_context_keys_by_label = {
                "appliance_clothes_washer": ["Rated Annual Consumption [kWh/yr]"],
                "appliance_clothes_dryer": ["Efficiency [lb/kWh]"],
                "appliance_dishwasher": ["Efficiency [kWh/yr or #]"],
                "appliance_refrigerator": ["Rated Annual Consumption [kWh/yr]"],
                "appliance_extra_refrigerator": ["Rated Annual Consumption [kWh/yr]"],
                "appliance_dehumidifier": ["Efficiency [liters/kWh]", "Capacity [pints/day]"],
                "appliance_dehumidifier_setpoint": ["Relative Humidity [frac]"],
            }
            preferred_context_keys = preferred_context_keys_by_label.get(
                context_label,
                ["Usage Multiplier", "Rated Annual Consumption [kWh/yr]", "Efficiency [ft3/kWh-cyc]", "Efficiency [lb/kWh]", "Efficiency [kWh/yr or #]", "Efficiency [liters/kWh]", "Capacity [ft3]", "Capacity [pints/day]"],
            )
            for context_key in preferred_context_keys:
                context_value = best_row.get(context_key)
                if context_value is None:
                    continue
                context_text = str(context_value).strip()
                if context_text == "":
                    continue
                context_label_name = context_key
                context_value_text = context_text
                break
        context_suffix = f" : {context_label_name}: {context_value_text}" if context_label_name is not None else ""
        _log_approximation_warning_once(
            (context_label, best_name),
            "Approximated %s option using nearest match '%s'%s\n  target values:\n%s",
            context_label,
            best_name,
            context_suffix,
            _format_target_values_block(target_values),
        )

    return best_name


def _update_appliance_clothes_washer_column(df, clothes_washer_rows):
    if "appliance_clothes_washer" not in df.columns:
        df["appliance_clothes_washer"] = None

    for idx, row in df.iterrows():
        if _to_bool(row.get("clothes_washer_present"), default=False):
            target_values = {
                "Efficiency Type": row.get("clothes_washer_efficiency_type"),
                "Efficiency [ft3/kWh-cyc]": row.get("clothes_washer_efficiency"),
                "Rated Annual Consumption [kWh/yr]": row.get("clothes_washer_rated_annual_kwh"),
                "Label Electric Rate [$/kWh]": row.get("clothes_washer_label_electric_rate"),
                "Label Gas Rate [$/therm]": row.get("clothes_washer_label_gas_rate"),
                "Label Annual Gas Cost [$]": row.get("clothes_washer_label_annual_gas_cost"),
                "Label Usage [cyc/wk]": row.get("clothes_washer_label_usage"),
                "Capacity [ft3]": row.get("clothes_washer_capacity"),
                "Usage Multiplier": row.get("clothes_washer_usage_multiplier"),
                "Location": row.get("clothes_washer_location"),
            }
            field_weights = {
                "Rated Annual Consumption [kWh/yr]": 10.0,
                "Efficiency Type": 4.0,
                "Efficiency [ft3/kWh-cyc]": 4.0,
                "Capacity [ft3]": 2.0,
                "Label Electric Rate [$/kWh]": 1.0,
                "Label Gas Rate [$/therm]": 1.0,
                "Label Annual Gas Cost [$]": 1.0,
                "Label Usage [cyc/wk]": 1.0,
                "Usage Multiplier": 1.0,
                "Location": 0.0,
            }
            df.at[idx, "appliance_clothes_washer"] = (
                _match_choice_option_by_tsv_properties(
                    clothes_washer_rows,
                    target_values,
                    "appliance_clothes_washer",
                    field_weights,
                )
                or "None"
            )
        else:
            df.at[idx, "appliance_clothes_washer"] = "None"

    return df


def _update_appliance_clothes_dryer_column(df, clothes_dryer_rows):
    if "appliance_clothes_dryer" not in df.columns:
        df["appliance_clothes_dryer"] = None

    for idx, row in df.iterrows():
        if _to_bool(row.get("clothes_dryer_present"), default=False):
            vented_flow_rate = _to_optional_float(row.get("clothes_dryer_vented_flow_rate"))
            efficiency_type = _normalize_legacy_value(row.get("clothes_dryer_efficiency_type"))
            efficiency = _to_optional_float(row.get("clothes_dryer_efficiency"))
            fuel_type = _normalize_legacy_value(row.get("clothes_dryer_fuel_type"))
            if vented_flow_rate is not None and vented_flow_rate > 0:
                drying_method = "conventional"
            elif fuel_type == "electricity" and efficiency_type == "energyfactor" and efficiency is not None and efficiency >= 4.0:
                drying_method = "condensing"
            elif fuel_type == "electricity" and efficiency_type == "combinedenergyfactor" and efficiency is not None and efficiency >= 5.0:
                drying_method = "heat pump"
            else:
                drying_method = "conventional"

            target_values = {
                "Efficiency Type": row.get("clothes_dryer_efficiency_type"),
                "Efficiency [lb/kWh]": row.get("clothes_dryer_efficiency"),
                "Fuel Type": row.get("clothes_dryer_fuel_type"),
                "Drying Method": drying_method,
                "Usage Multiplier": row.get("clothes_dryer_usage_multiplier"),
                "Location": row.get("clothes_dryer_location"),
            }
            field_weights = {
                "Efficiency Type": 5.0,
                "Efficiency [lb/kWh]": 8.0,
                "Fuel Type": 5.0,
                "Drying Method": 8.0,
                "Usage Multiplier": 1.0,
                "Location": 0.0,
            }
            df.at[idx, "appliance_clothes_dryer"] = (
                _match_choice_option_by_tsv_properties(
                    clothes_dryer_rows,
                    target_values,
                    "appliance_clothes_dryer",
                    field_weights,
                )
                or "None"
            )
        else:
            df.at[idx, "appliance_clothes_dryer"] = "None"

    return df


def _update_appliance_dishwasher_column(df, dishwasher_rows):
    if "appliance_dishwasher" not in df.columns:
        df["appliance_dishwasher"] = None

    for idx, row in df.iterrows():
        if _to_bool(row.get("dishwasher_present"), default=False):
            target_values = {
                "Efficiency Type": row.get("dishwasher_efficiency_type"),
                "Efficiency [kWh/yr or #]": row.get("dishwasher_efficiency"),
                "Label Electric Rate [$/kWh]": row.get("dishwasher_label_electric_rate"),
                "Label Gas Rate [$/therm]": row.get("dishwasher_label_gas_rate"),
                "Label Annual Gas Cost [$]": row.get("dishwasher_label_annual_gas_cost"),
                "Label Usage [cyc/wk]": row.get("dishwasher_label_usage"),
                "Place Setting Capacity [#]": row.get("dishwasher_place_setting_capacity"),
                "Usage Multiplier": row.get("dishwasher_usage_multiplier"),
                "Location": row.get("dishwasher_location"),
            }
            field_weights = {
                "Efficiency Type": 5.0,
                "Efficiency [kWh/yr or #]": 8.0,
                "Label Electric Rate [$/kWh]": 1.0,
                "Label Gas Rate [$/therm]": 1.0,
                "Label Annual Gas Cost [$]": 1.0,
                "Label Usage [cyc/wk]": 1.0,
                "Place Setting Capacity [#]": 4.0,
                "Usage Multiplier": 1.0,
                "Location": 0.0,
            }
            df.at[idx, "appliance_dishwasher"] = (
                _match_choice_option_by_tsv_properties(
                    dishwasher_rows,
                    target_values,
                    "appliance_dishwasher",
                    field_weights,
                )
                or "None"
            )
        else:
            df.at[idx, "appliance_dishwasher"] = "None"

    return df


def _update_appliance_refrigerator_column(df, refrigerator_rows):
    if "appliance_refrigerator" not in df.columns:
        df["appliance_refrigerator"] = None

    for idx, row in df.iterrows():
        if _to_bool(row.get("refrigerator_present"), default=False):
            target_values = {
                "Rated Annual Consumption [kWh/yr]": row.get("refrigerator_rated_annual_kwh"),
                "Usage Multiplier": row.get("refrigerator_usage_multiplier"),
                "Location": row.get("refrigerator_location"),
            }
            field_weights = {
                "Rated Annual Consumption [kWh/yr]": 10.0,
                "Usage Multiplier": 1.0,
                "Location": 0.0,
            }
            df.at[idx, "appliance_refrigerator"] = (
                _match_choice_option_by_tsv_properties(
                    refrigerator_rows,
                    target_values,
                    "appliance_refrigerator",
                    field_weights,
                )
                or "None"
            )
        else:
            df.at[idx, "appliance_refrigerator"] = "None"

    return df


def _update_appliance_extra_refrigerator_column(df, extra_refrigerator_rows):
    if "appliance_extra_refrigerator" not in df.columns:
        df["appliance_extra_refrigerator"] = None

    for idx, row in df.iterrows():
        if _to_bool(row.get("extra_refrigerator_present"), default=False):
            target_values = {
                "Rated Annual Consumption [kWh/yr]": row.get("extra_refrigerator_rated_annual_kwh"),
                "Usage Multiplier": row.get("extra_refrigerator_usage_multiplier"),
                "Location": row.get("extra_refrigerator_location"),
            }
            field_weights = {
                "Rated Annual Consumption [kWh/yr]": 10.0,
                "Usage Multiplier": 1.0,
                "Location": 0.0,
            }
            df.at[idx, "appliance_extra_refrigerator"] = (
                _match_choice_option_by_tsv_properties(
                    extra_refrigerator_rows,
                    target_values,
                    "appliance_extra_refrigerator",
                    field_weights,
                )
                or "None"
            )
        else:
            df.at[idx, "appliance_extra_refrigerator"] = "None"

    return df


def _update_appliance_dehumidifier_column(df, dehumidifier_rows):
    if "appliance_dehumidifier" not in df.columns:
        df["appliance_dehumidifier"] = None

    for idx, row in df.iterrows():
        dehumidifier_type = _normalize_legacy_value(row.get("dehumidifier_type"))
        if dehumidifier_type not in {"", "none"}:
            target_values = {
                "Type": row.get("dehumidifier_type"),
                "Efficiency Type": row.get("dehumidifier_efficiency_type"),
                "Efficiency [liters/kWh]": row.get("dehumidifier_efficiency"),
                "Capacity [pints/day]": row.get("dehumidifier_capacity"),
            }
            field_weights = {
                "Type": 4.0,
                "Efficiency Type": 5.0,
                "Efficiency [liters/kWh]": 8.0,
                "Capacity [pints/day]": 4.0,
            }
            df.at[idx, "appliance_dehumidifier"] = (
                _match_choice_option_by_tsv_properties(
                    dehumidifier_rows,
                    target_values,
                    "appliance_dehumidifier",
                    field_weights,
                )
                or "None"
            )
        else:
            df.at[idx, "appliance_dehumidifier"] = "None"

    return df


def _update_appliance_dehumidifier_setpoint_column(df, dehumidifier_setpoint_rows):
    if "appliance_dehumidifier_setpoint" not in df.columns:
        df["appliance_dehumidifier_setpoint"] = None

    for idx, row in df.iterrows():
        dehumidifier_type = _normalize_legacy_value(row.get("dehumidifier_type"))
        if dehumidifier_type not in {"", "none"}:
            setpoint_value = _to_optional_float(row.get("dehumidifier_rh_setpoint"))
            if setpoint_value is not None:
                df.at[idx, "appliance_dehumidifier_setpoint"] = (
                    _match_choice_option_by_tsv_properties(
                        dehumidifier_setpoint_rows,
                        {"Relative Humidity [frac]": setpoint_value},
                        "appliance_dehumidifier_setpoint",
                        {"Relative Humidity [frac]": 10.0},
                    )
                    or "50% RH"
                )
            else:
                df.at[idx, "appliance_dehumidifier_setpoint"] = "50% RH"
        else:
            df.at[idx, "appliance_dehumidifier_setpoint"] = "50% RH"

    return df


def update_appliances_v110_to_v112(df):
    """Map legacy appliance columns to the v1.12 appliance choice strings."""
    reset_approximation_warning_cache()

    legacy_columns = [
        "clothes_dryer_present",
        "clothes_dryer_fuel_type",
        "clothes_dryer_efficiency_type",
        "clothes_dryer_efficiency",
        "clothes_dryer_vented_flow_rate",
        "clothes_dryer_usage_multiplier",
        "clothes_dryer_location",
        "clothes_washer_present",
        "clothes_washer_efficiency_type",
        "clothes_washer_efficiency",
        "clothes_washer_rated_annual_kwh",
        "clothes_washer_label_electric_rate",
        "clothes_washer_label_gas_rate",
        "clothes_washer_label_annual_gas_cost",
        "clothes_washer_label_usage",
        "clothes_washer_capacity",
        "clothes_washer_usage_multiplier",
        "clothes_washer_location",
        "dishwasher_present",
        "dishwasher_efficiency_type",
        "dishwasher_efficiency",
        "dishwasher_label_electric_rate",
        "dishwasher_label_gas_rate",
        "dishwasher_label_annual_gas_cost",
        "dishwasher_label_usage",
        "dishwasher_place_setting_capacity",
        "dishwasher_usage_multiplier",
        "dishwasher_location",
        "refrigerator_present",
        "refrigerator_rated_annual_kwh",
        "refrigerator_usage_multiplier",
        "refrigerator_location",
        "extra_refrigerator_present",
        "extra_refrigerator_rated_annual_kwh",
        "extra_refrigerator_usage_multiplier",
        "extra_refrigerator_location",
        "dehumidifier_type",
        "dehumidifier_efficiency_type",
        "dehumidifier_efficiency",
        "dehumidifier_capacity",
        "dehumidifier_rh_setpoint",
        "dehumidifier_fraction_dehumidification_load_served",
    ]
    if not any(column in df.columns for column in legacy_columns):
        return df

    clothes_washer_rows = get_tsv_data(str(_option_tsv_path("appliance_clothes_washer.tsv")))
    clothes_dryer_rows = get_tsv_data(str(_option_tsv_path("appliance_clothes_dryer.tsv")))
    dishwasher_rows = get_tsv_data(str(_option_tsv_path("appliance_dishwasher.tsv")))
    refrigerator_rows = get_tsv_data(str(_option_tsv_path("appliance_refrigerator.tsv")))
    extra_refrigerator_rows = get_tsv_data(str(_option_tsv_path("appliance_extra_refrigerator.tsv")))
    dehumidifier_rows = get_tsv_data(str(_option_tsv_path("appliance_dehumidifier.tsv")))
    dehumidifier_setpoint_rows = get_tsv_data(str(_option_tsv_path("appliance_dehumidifier_setpoint.tsv")))

    _update_appliance_clothes_washer_column(df, clothes_washer_rows)
    _update_appliance_clothes_dryer_column(df, clothes_dryer_rows)
    _update_appliance_dishwasher_column(df, dishwasher_rows)
    _update_appliance_refrigerator_column(df, refrigerator_rows)
    _update_appliance_extra_refrigerator_column(df, extra_refrigerator_rows)
    _update_appliance_dehumidifier_column(df, dehumidifier_rows)
    _update_appliance_dehumidifier_setpoint_column(df, dehumidifier_setpoint_rows)

    return drop_legacy_columns(
        df,
        legacy_columns,
        "Dropping legacy appliance columns after mapping to v1.12 appliance options.",
    )

def update_duct_leakage_v110_to_v112(df):
    """Map legacy duct leakage/insulation columns to the v1.12 hvac_ducts option string."""

    tsv_path = _option_tsv_path("hvac_ducts.tsv")
    rows = get_tsv_data(str(tsv_path))
    option_names = get_option_names(str(tsv_path))
    option_names_lower = {name.lower(): name for name in option_names}

    if "hvac_ducts" not in df.columns:
        df["hvac_ducts"] = None

    valid_option_rows = []
    for row in rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue
        valid_option_rows.append(row)

    for idx, row in df.iterrows():
        # Keep already valid v1.12 options as-is.
        current = str(row.get("hvac_ducts", "")).strip()
        if current != "" and current.lower() in option_names_lower:
            df.at[idx, "hvac_ducts"] = option_names_lower[current.lower()]
            continue

        # Resolve explicit no-ducts signals from either hvac_ducts or legacy non-HPXML field.
        hvac_has_ducts = row.get("HVAC Has Ducts")
        no_ducts_signal = (
            _normalize_legacy_value(current) in {"none", "noducts", "aucun", "no"}
            or _normalize_legacy_value(hvac_has_ducts) in {"no", "non", "false", "0", "aucun"}
        )
        if no_ducts_signal:
            df.at[idx, "hvac_ducts"] = "None"
            continue

        units = _normalize_duct_leakage_units(row.get("ducts_leakage_units"))
        supply_leak = _to_optional_float(row.get("ducts_supply_leakage_to_outside_value"))
        return_leak = _to_optional_float(row.get("ducts_return_leakage_to_outside_value"))
        supply_r = _to_optional_float(row.get("ducts_supply_insulation_r"))
        return_r = _to_optional_float(row.get("ducts_return_insulation_r"))

        if units == "Percent":
            supply_leak = _normalize_percent_value(supply_leak)
            return_leak = _normalize_percent_value(return_leak)

        # Legacy files generally provide both values. If one is missing, mirror the other.
        if supply_leak is None and return_leak is not None:
            supply_leak = return_leak
        if return_leak is None and supply_leak is not None:
            return_leak = supply_leak

        if supply_r is None and return_r is not None:
            supply_r = return_r
        if return_r is None and supply_r is not None:
            return_r = supply_r

        leak_total = None
        if supply_leak is not None and return_leak is not None:
            leak_total = supply_leak + return_leak

        if units is None or leak_total is None:
            continue

        if supply_r is None:
            supply_r = 0.0
        if return_r is None:
            return_r = 0.0

        # Detailed options encode explicit supply leakage fraction; preserve when available.
        supply_fraction = None
        if leak_total > 0:
            supply_fraction = supply_leak / leak_total

        best_name = None
        best_score = None

        for opt in valid_option_rows:
            opt_name = str(opt.get("Option Name", "")).strip()
            opt_units = str(opt.get("Leakage Units", "")).strip()
            if _normalize_legacy_value(opt_units) != _normalize_legacy_value(units):
                continue

            opt_leak = _to_optional_float(opt.get("Leakage to Outside Value"))
            opt_supply_r = _to_optional_float(opt.get("Supply Insulation R-Value [F-ft2-hr/Btu]"))
            opt_return_r = _to_optional_float(opt.get("Return Insulation R-Value [F-ft2-hr/Btu]"))
            opt_supply_frac = _to_optional_float(opt.get("Supply Leakage Fraction [frac]"))

            if opt_leak is None or opt_supply_r is None or opt_return_r is None:
                continue

            score = abs(opt_leak - leak_total)
            score += 0.02 * abs(opt_supply_r - supply_r)
            score += 0.02 * abs(opt_return_r - return_r)

            if supply_fraction is not None:
                if opt_supply_frac is None:
                    # Prefer detailed options when legacy split is not 50/50.
                    score += 0.3 if abs(supply_fraction - 0.5) > 1e-6 else 0
                else:
                    score += 0.1 * abs(opt_supply_frac - supply_fraction)

            if best_score is None or score < best_score:
                best_score = score
                best_name = opt_name

        if best_name is not None:
            df.at[idx, "hvac_ducts"] = option_names_lower.get(best_name.lower(), best_name)

    old_columns = [
        "ducts_leakage_units",
        "ducts_supply_leakage_to_outside_value",
        "ducts_supply_insulation_r",
        "ducts_return_leakage_to_outside_value",
        "ducts_return_insulation_r",
    ]
    cols_to_drop = [c for c in old_columns if c in df.columns]
    if len(cols_to_drop) > 0:
        df.drop(columns=cols_to_drop, inplace=True)

    return df

def update_v110_to_v112(input_filePath, output_filePath):
    """
    Update the CSV file from version 1.10 to version 1.12.

    Performs the migration steps needed for the v1.10 -> v1.12 input format.

    Args:
        input_filePath (str): The path to the input CSV file.
        output_filePath (str): The path to the output CSV file.
    """
    # Load CSV once
    df = pd.read_csv(input_filePath, dtype=str, keep_default_na=False)

    # Apply v1.10→v1.12 value replacements
    df = update_column_values_v110_to_v112(df)

    # Drop deprecated or renamed simulation-control/site columns and convert geometry inputs.
    df = update_simulation_control_daylight_saving_enabled_v110_to_v112(df)
    df = update_site_time_zone_utc_offset_v110_to_v112(df)
    df = update_geometry_building_num_units_v110_to_v112(df)
    df = update_year_built_v110_to_v112(df)
    df = update_geometry_unit_cfa_v110_to_v112(df)
    df = update_geometry_average_ceiling_height_v110_to_v112(df)
    df = update_geometry_unit_orientation_v110_to_v112(df)

    # Create enclosure_air_leakage column from v1.10 component columns
    df = update_air_leakage_v110_to_v112(df)

    # Update geometry_unit column from v1.10→v1.12 migration
    df = update_geometry_unit_v110_to_v112(df)

    # Update geometry_attic_type to option-based values
    df = update_geometry_attic_v110_to_v112(df)

    # Update window and skylight thermal properties and geometry strings
    df = update_enclosure_window_v110_to_v112(df)
    df = update_enclosure_skylight_v110_to_v112(df)
    df = update_geometry_window_areas_or_wwrs_v110_to_v112(df)
    df = update_geometry_skylight_areas_v110_to_v112(df)
    df = update_window_interior_shading_v110_to_v112(df)

    ## todo validate in legacy before implementing this
    # Update geometry_foundation_type to option-based values
    df = update_geometry_foundation_v110_to_v112(df)

    # Update foundation wall option string from type and insulation fields
    df = update_enclosure_foundation_wall_v110_to_v112(df)

    # Update opaque enclosure assemblies and thermal layers
    df = update_enclosure_wall_v110_to_v112(df)
    df = update_enclosure_ceiling_v110_to_v112(df)
    df = update_enclosure_floor_over_foundation_v110_to_v112(df)
    df = update_enclosure_floor_over_garage_v110_to_v112(df)
    df = update_enclosure_slab_v110_to_v112(df)

    # Update tp enclosure_overhangs
    df = update_enclosure_overhangs_v110_to_v112(df)

    # Update pool_parameters column from v1.10→v1.12 migration
    df = update_pool_parameters_v110_to_v112(df)

    # Update legacy duct leakage/insulation columns to hvac_ducts option values
    df = update_duct_leakage_v110_to_v112(df)

    # Update legacy water heater columns to dhw_water_heater and dhw_water_heater_location
    df = update_dhw_water_heater_v110_to_v112(df)

    # Update legacy ventilation columns to v1.12 ventilation option strings
    df = update_ventilation_v110_to_v112(df)

    # Update legacy appliance columns to v1.12 appliance option strings
    df = update_appliances_v110_to_v112(df)

    # Update heat pump option strings from legacy v1.10 inputs
    df = update_heat_pump_v110_to_v112(df)

    # Save the updated CSV
    df.to_csv(output_filePath, index=False)
    print(f"  ✓ Replaced 'none' → 'not present' (5 columns)")
    print("  ✓ Updated first five migration columns")
    print(f"  ✓ Created enclosure_air_leakage column")


def update_heat_pump_v110_to_v112(df):
    """Map legacy v1.10 heat pump inputs to canonical v1.12 option strings."""

    if "heat_pump_type" not in df.columns:
        return df

    hvac_tsv_path = _option_tsv_path("hvac_heat_pump.tsv")
    backup_tsv_path = _option_tsv_path("hvac_heat_pump_backup.tsv")
    temp_tsv_path = _option_tsv_path("hvac_heat_pump_temperatures.tsv")

    hvac_rows = get_tsv_data(str(hvac_tsv_path))
    backup_rows = get_tsv_data(str(backup_tsv_path))
    temp_rows = get_tsv_data(str(temp_tsv_path))

    hvac_option_names = get_option_names(str(hvac_tsv_path))
    hvac_option_names_lower = {name.lower(): name for name in hvac_option_names}
    backup_option_names = get_option_names(str(backup_tsv_path))
    backup_option_names_lower = {name.lower(): name for name in backup_option_names}
    temp_option_names = get_option_names(str(temp_tsv_path))
    temp_option_names_lower = {name.lower(): name for name in temp_option_names}

    def _normalize_type(value):
        if value is None:
            return ""
        key = str(value).strip().lower()
        key = key.replace("_", " ")
        aliases = {
            "airtoair": "air-to-air",
            "mini split": "mini-split",
            "minisplit": "mini-split",
            "groundtoair": "ground-to-air",
            "packaged terminal heat pump": "packaged terminal heat pump",
            "packagedterminalheatpump": "packaged terminal heat pump",
            "room air conditioner with reverse cycle": "room air conditioner with reverse cycle",
            "roomairconditionerwithreversecycle": "room air conditioner with reverse cycle",
        }
        return aliases.get(key, key)

    def _legacy_efficiency_value(value, eff_type):
        fval = _to_optional_float(value)
        if fval is None:
            return None
        if eff_type in {"SEER", "HSPF", "EER", "CEER", "COP"}:
            return fval
        if eff_type == "SEER2":
            return fval
        if eff_type == "HSPF2":
            return fval
        return fval

    def _match_hvac_heat_pump(row):
        legacy_type = _normalize_type(row.get("heat_pump_type"))
        legacy_heating_type = str(row.get("heat_pump_heating_efficiency_type", "")).strip()
        legacy_cooling_type = str(row.get("heat_pump_cooling_efficiency_type", "")).strip()
        legacy_heating_eff = _to_optional_float(row.get("heat_pump_heating_efficiency"))
        legacy_cooling_eff = _to_optional_float(row.get("heat_pump_cooling_efficiency"))
        legacy_comp = str(row.get("heat_pump_cooling_compressor_type", "")).strip().lower()

        if legacy_type in {"", "none", "not present"}:
            return "None"

        best_name = None
        best_score = None
        for opt in hvac_rows:
            option_name = str(opt.get("Option Name", "")).strip()
            if option_name == "" or option_name.startswith("#"):
                continue
            opt_type = _normalize_type(opt.get("Type", ""))
            if opt_type != legacy_type:
                continue

            opt_comp = str(opt.get("Cooling Compressor Type", "")).strip().lower()
            if legacy_comp and opt_comp and legacy_comp != opt_comp:
                continue

            opt_cooling_type = str(opt.get("Cooling Efficiency Type", "")).strip()
            opt_heating_type = str(opt.get("Heating Efficiency Type", "")).strip()
            opt_hval = _to_optional_float(opt.get("Heating Efficiency"))
            opt_cval = _to_optional_float(opt.get("Cooling Efficiency"))

            if legacy_heating_type and opt_heating_type and legacy_heating_type != opt_heating_type:
                if legacy_heating_type == "HSPF" and opt_heating_type == "HSPF2":
                    exp = legacy_heating_eff * 0.85 if legacy_heating_eff is not None else None
                elif legacy_heating_type == "HSPF2" and opt_heating_type == "HSPF":
                    exp = legacy_heating_eff / 0.85 if legacy_heating_eff is not None else None
                else:
                    exp = None
                if exp is None:
                    continue
                score = abs(exp - opt_hval) if opt_hval is not None else 1e6
            elif legacy_heating_eff is not None and opt_hval is not None:
                score = abs(legacy_heating_eff - opt_hval)
            else:
                score = 0.0

            if legacy_cooling_type and opt_cooling_type and legacy_cooling_type != opt_cooling_type:
                if legacy_cooling_type == "SEER" and opt_cooling_type == "SEER2":
                    exp = legacy_cooling_eff * 0.95 if legacy_cooling_eff is not None else None
                elif legacy_cooling_type == "SEER2" and opt_cooling_type == "SEER":
                    exp = legacy_cooling_eff / 0.95 if legacy_cooling_eff is not None else None
                else:
                    exp = None
                if exp is None:
                    continue
                score += abs(exp - opt_cval) if opt_cval is not None else 1e6
            elif legacy_cooling_eff is not None and opt_cval is not None:
                score += abs(legacy_cooling_eff - opt_cval)
            else:
                score += 0.0

            if best_score is None or score < best_score:
                best_score = score
                best_name = option_name

        if best_name is None:
            direct = hvac_option_names_lower.get(str(row.get("heat_pump_type", "")).strip().lower())
            if direct is not None:
                return direct
            logger.warning(
                "No hvac_heat_pump match for legacy heat_pump_type '%s' with efficiencies %s/%s.",
                legacy_type,
                legacy_heating_eff,
                legacy_cooling_eff,
            )
            return "None"

        return best_name

    def _format_percent_value(value):
        fval = _to_optional_float(value)
        if fval is None:
            return None
        return fval / 100.0 if fval > 1.0 else fval

    def _match_backup_option(row):
        legacy_type = str(row.get("heat_pump_backup_type", "")).strip().lower()
        if legacy_type in {"", "none", "not present"}:
            return "None"
        if legacy_type == "separate":
            return "Separate Heating System"

        fuel = str(row.get("heat_pump_backup_fuel", "")).strip().lower()
        eff = _to_optional_float(row.get("heat_pump_backup_heating_efficiency"))
        if fuel == "" or eff is None:
            return "None"

        best_name = None
        best_score = None
        for opt in backup_rows:
            option_name = str(opt.get("Option Name", "")).strip()
            if option_name == "" or option_name.startswith("#"):
                continue
            opt_type = str(opt.get("Type", "")).strip().lower()
            if opt_type != "integrated":
                continue
            opt_fuel = str(opt.get("Fuel", "")).strip().lower()
            if fuel != opt_fuel:
                continue
            opt_eff = _to_optional_float(opt.get("Heating Efficiency [Frac]"))
            if opt_eff is None:
                continue
            normalized_eff = _format_percent_value(eff)
            score = abs(normalized_eff - opt_eff) if normalized_eff is not None else 1e6
            if best_score is None or score < best_score:
                best_score = score
                best_name = option_name

        if best_name is None:
            direct = backup_option_names_lower.get(
                f"integrated, {fuel}, {str(row.get('heat_pump_backup_heating_efficiency', '')).strip()}".lower()
            )
            if direct is not None:
                return direct
            logger.warning(
                "No hvac_heat_pump_backup match for legacy values type='%s', fuel='%s', eff='%s'.",
                legacy_type,
                fuel,
                row.get("heat_pump_backup_heating_efficiency"),
            )
            return "None"
        return best_name

    def _match_temperature_option(row):
        compressor = _to_optional_float(row.get("heat_pump_compressor_lockout_temp"))
        backup_lock = _to_optional_float(row.get("heat_pump_backup_heating_lockout_temp"))

        if compressor is None and backup_lock is None:
            return "None"

        if compressor is not None and backup_lock is not None:
            target = str(row.get("heat_pump_compressor_lockout_temp", "")).strip()
            if abs(compressor - backup_lock) < 1e-6:
                exact = f"{int(round(compressor))}F Min Compressor Temp, {int(round(compressor))}F Max HP Backup Temp"
                if exact in temp_option_names_lower:
                    return temp_option_names_lower[exact]
                return f"{int(round(compressor))}F Min Compressor Temp"
            exact_name = f"{int(round(compressor))}F Min Compressor Temp"
            if exact_name in temp_option_names_lower:
                return temp_option_names_lower[exact_name]
            if backup_lock is not None:
                return f"{int(round(compressor))}F Min Compressor Temp"

        if compressor is not None:
            val = int(round(compressor))
            exact = f"{val}F Min Compressor Temp"
            if exact in temp_option_names_lower:
                return temp_option_names_lower[exact]
            return exact

        if backup_lock is not None:
            val = int(round(backup_lock))
            exact = f"{val}F Min Compressor Temp"
            if exact in temp_option_names_lower:
                return temp_option_names_lower[exact]
            return exact

        return "None"

    def _match_fraction_option(row, value_col, tsv_name):
        if value_col not in row or pd.isna(row.get(value_col)):
            return None
        fraction = _to_optional_float(row.get(value_col))
        if fraction is None:
            return None
        if fraction < 0.0:
            fraction = 0.0
        if fraction > 1.0:
            fraction = fraction / 100.0

        tsv_path = _option_tsv_path(tsv_name)
        rows = get_tsv_data(str(tsv_path))
        best_name = None
        best_score = None
        for opt in rows:
            option_name = str(opt.get("Option Name", "")).strip()
            if option_name == "" or option_name.startswith("#"):
                continue
            opt_value = _to_optional_float(opt.get("Fraction"))
            if opt_value is None:
                continue
            score = abs(fraction - opt_value)
            if best_score is None or score < best_score:
                best_score = score
                best_name = option_name
        if best_name is None:
            return None
        return best_name

    for idx, row in df.iterrows():
        df.at[idx, "hvac_heat_pump"] = _match_hvac_heat_pump(row)
        df.at[idx, "hvac_heat_pump_heating_load_served"] = _match_fraction_option(
            row, "heat_pump_fraction_heat_load_served", "hvac_heat_pump_heating_load_served.tsv"
        )
        df.at[idx, "hvac_heat_pump_cooling_load_served"] = _match_fraction_option(
            row, "heat_pump_fraction_cool_load_served", "hvac_heat_pump_cooling_load_served.tsv"
        )
        df.at[idx, "hvac_heat_pump_temperatures"] = _match_temperature_option(row)
        df.at[idx, "hvac_heat_pump_backup"] = _match_backup_option(row)

    old_columns = [
        "heat_pump_type",
        "heat_pump_heating_efficiency_type",
        "heat_pump_heating_efficiency",
        "heat_pump_cooling_efficiency_type",
        "heat_pump_cooling_efficiency",
        "heat_pump_cooling_compressor_type",
        "heat_pump_fraction_heat_load_served",
        "heat_pump_fraction_cool_load_served",
        "heat_pump_compressor_lockout_temp",
        "heat_pump_backup_type",
        "heat_pump_backup_fuel",
        "heat_pump_backup_heating_efficiency",
        "heat_pump_backup_heating_lockout_temp",
    ]
    for col in old_columns:
        if col in df.columns:
            df.drop(columns=[col], inplace=True)

    return df


def update_heat_pummp_v110_to_v112(df):
    """Backward-compatible alias for the heat pump migration function."""
    return update_heat_pump_v110_to_v112(df)

def main(input_filePath, output_filePath=None):
    """
    Main function to migrate CSV file from v1.10 to v1.12.

    Args:
        input_filePath (str): Path to input CSV file (required)
        output_filePath (str, optional): Path to output CSV file. If not provided,
                                         creates output in v1.12/ subdirectory with -1.12 suffix
    """
    # Validate input file exists
    if not os.path.isfile(input_filePath):
        raise FileNotFoundError(f"Input file not found: {input_filePath}")

    # Generate default output path if not provided
    if output_filePath is None:
        input_path = Path(input_filePath)
        v112_dir = input_path.parent / "v1.12"
        v112_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem
        output_filePath = v112_dir / f"{stem}-1.12{input_path.suffix}"

    # Convert Path object to string if needed
    output_filePath = str(output_filePath)

    # Ensure output file path is different from input file path
    if os.path.abspath(input_filePath) == os.path.abspath(output_filePath):
        raise ValueError(
            "Output file path must be different from input file path to avoid overwriting the original file."
        )

    print(f"Migrating: {input_filePath}")
    print(f"Output:    {output_filePath}")

    update_v110_to_v112(input_filePath, output_filePath)

    print(f"✓ Migration complete: {output_filePath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate CSV files from HPXML v1.10 to v1.12 format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            # Migrate with auto-generated output path (creates v1.12/ subdirectory)
            python migrate_csv.py input.csv
            # Migrate to specific output path
            python migrate_csv.py input.csv output.csv
            """,
    )

    parser.add_argument(
        "input", metavar="INPUT_FILE", help="Path to input CSV file (required)"
    )

    parser.add_argument(
        "output",
        metavar="OUTPUT_FILE",
        nargs="?",
        default=None,
        help="Path to output CSV file (optional; default: INPUT_FILE-1.12.csv in v1.12/ subdirectory)",
    )

    args = parser.parse_args()

    try:
        main(args.input, args.output)
    except Exception as e:
        print(f"✗ Error: {e}")
        exit(1)
