"""
Migrate old CSV files to the new format. from HPXML 4.1 to 5.0
This script is used to convert CSV files that were created with an older version of the simulator to the new format
that is compatible with the current version.
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import argparse
import os
import logging
from read_option_tsv import get_tsv_data, get_option_names
from utils import (
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

    Performs two migrations:
    1. Replaces "none" with "not present" in 5 HPXML fields
    2. Creates enclosure_air_leakage column from v1.10 air leakage component columns

    Args:
        input_filePath (str): The path to the input CSV file.
        output_filePath (str): The path to the output CSV file.
    """
    # Load CSV once
    df = pd.read_csv(input_filePath, dtype=str, keep_default_na=False)

    # Apply v1.10→v1.12 value replacements
    df = update_column_values_v110_to_v112(df)

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

    # Save the updated CSV
    df.to_csv(output_filePath, index=False)
    print(f"  ✓ Replaced 'none' → 'not present' (5 columns)")
    print(f"  ✓ Created enclosure_air_leakage column")


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
