"""
Migrate old CSV files to the new format. from HPXML 4.1 to 5.0
This script is used to convert CSV files that were created with an older version of the simulator to the new format
that is compatible with the current version.
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import argparse
import os
import logging

from migration.src.utils.read_option_tsv import get_tsv_data, get_option_names
from migration.src.utils.constants import (
    GEOMETRY_CEILING_HEIGHT_CHOICES,
    GEOMETRY_UNIT_DIRECTION_CHOICES,
)
from migration.src.utils.migration_helper import (
    format_ceiling_height_choice,
    format_unit_direction_choice,
)
from migration.src.utils.utils import (
    _build_geometry_unit_lookup,
    _build_misc_option_from_legacy,
    _legacy_overhang_cols,
    _match_enclosure_option,
    _normalize_duct_leakage_units,
    _normalize_legacy_value,
    _normalize_percent_value,
    _option_tsv_path,
    _to_float,
    _to_optional_float,
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
        if mapped is None:
            candidates = by_attic_type.get(attic_key, [])
            if len(candidates) == 1:
                mapped = candidates[0]
            elif len(candidates) > 1:
                gable = [c for c in candidates if "gable" in c.lower()]
                mapped = gable[0] if gable else candidates[0]

        if mapped is None:
            logger.warning(
                f"No attic option match for geometry_attic_type '{old_attic}' and geometry_roof_type '{old_roof}'."
            )
            continue

        df.at[idx, "geometry_attic_type"] = mapped

    df.drop(columns=["geometry_roof_type"], inplace=True)

    return df

def update_geometry_foundation_v110_to_v112(df):
    """Map legacy geometry_foundation_type values to v1.12 option names."""
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
            suffix = "Half Above-Grade"
            if "unconditioned" in mapped.lower():
                mapped = "Basement, Unconditioned, Half Above-Grade"
            elif "conditioned" in mapped.lower():
                mapped = "Basement, Conditioned, Half Above-Grade"
        elif legacy_key == "ventedcrawlspace" and hag is not None and hag > 3.0:
            mapped = "Detailed Example: Crawlspace, Vented, Above-Grade"

        df.at[idx, "geometry_foundation_type"] = mapped

    df.drop(columns=["geometry_foundation_height_above_grade"], inplace=True)
    df.drop(columns=["geometry_rim_joist_height"], inplace=True)
    df.drop(columns=["geometry_foundation_height"], inplace=True)

    return df

def update_enclosure_overhangs_v110_to_v112(df):
    """Map legacy detailed overhang columns to the v1.12 enclosure_overhangs option."""

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
                logger.warning(
                    f"Using nearest enclosure_overhangs option '{matched_name}' at row {idx}."
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

    ## todo validate in legacy before implementing this
    # Update geometry_foundation_type to option-based values
    df = update_geometry_foundation_v110_to_v112(df)

    # Update tp enclosure_overhangs
    df = update_enclosure_overhangs_v110_to_v112(df)

    # Update pool_parameters column from v1.10→v1.12 migration
    df = update_pool_parameters_v110_to_v112(df)

    # Update legacy duct leakage/insulation columns to hvac_ducts option values
    df = update_duct_leakage_v110_to_v112(df)

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
