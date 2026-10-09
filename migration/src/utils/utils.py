"""Shared migration helpers for multi-column assembly, TSV matching, and general value normalization."""

import logging
import re
from pathlib import Path

import pandas as pd

from migration.src.utils.read_option_tsv import get_tsv_data


logger = logging.getLogger(__name__)
_APPROXIMATION_WARNING_CACHE = set()


def reset_approximation_warning_cache():
    """Clear the per-run cache used to suppress repeated approximation warnings."""
    _APPROXIMATION_WARNING_CACHE.clear()


def _log_approximation_warning_once(cache_key, message, *args):
    """Log an approximation warning once per cache key during a migration run."""
    if cache_key in _APPROXIMATION_WARNING_CACHE:
        return
    _APPROXIMATION_WARNING_CACHE.add(cache_key)
    logger.warning(message, *args)


def _format_target_values_block(target_values):
    """Format target values as an indented multi-line block for log output."""
    lines = []
    for key, value in target_values.items():
        lines.append(f"    {key}: {value}")
    return "\n".join(lines)


def _build_geometry_unit_lookup(tsv_file_path):
    """Build a map of (facility_type_lower, stories_int) -> option name."""
    choices = {}
    for row in get_tsv_data(tsv_file_path):
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue

        facility_type = re.sub(
            r"[^a-z0-9]+", "", str(row.get("Facility Type", "")).strip().lower()
        )
        stories = row.get("Number of Stories", "")
        if facility_type == "" or stories == "":
            continue

        try:
            stories_int = int(float(str(stories)))
        except (ValueError, TypeError):
            continue

        choices[(facility_type, stories_int)] = option_name
    return choices


def _format_number_token(value):
    """Format a numeric token to a string, removing unnecessary decimal points for integers."""
    try:
        fval = float(str(value).strip())
    except (ValueError, TypeError):
        return None
    if fval.is_integer():
        return str(int(fval))
    return f"{fval:.12g}"


def _normalize_enclosure_value(text):
    """Normalize the enclosure_air_leakage value to a canonical format."""
    s = str(text).strip()
    s = re.sub(r"\s+", " ", s)

    m = re.match(r"^([0-9]*\.?[0-9]+)\s*(ACH|CFM)\s*([0-9]+)$", s, flags=re.IGNORECASE)
    if m:
        v = _format_number_token(m.group(1))
        p = _format_number_token(m.group(3))
        if (v is not None) and (p is not None):
            return f"{v} {m.group(2).upper()}{p}"

    m = re.match(r"^([0-9]*\.?[0-9]+)\s*(nACH|nCFM)$", s, flags=re.IGNORECASE)
    if m:
        v = _format_number_token(m.group(1))
        if v is not None:
            return f"{v} {m.group(2)}"

    return s


def _match_enclosure_option(raw_value, option_names):
    """Match the raw enclosure_air_leakage value to the closest option name."""
    normalized = _normalize_enclosure_value(raw_value)
    lookup = {name.lower(): name for name in option_names}
    direct = lookup.get(normalized.lower())
    if direct is not None:
        return direct

    m = re.match(
        r"^([0-9]*\.?[0-9]+)\s*(ACH|CFM)([0-9]+)$", normalized, flags=re.IGNORECASE
    )
    if m:
        target_val = float(m.group(1))
        target_kind = m.group(2).upper()
        target_pressure = int(float(m.group(3)))
        candidates = []
        for name in option_names:
            cm = re.match(
                r"^([0-9]*\.?[0-9]+)\s*(ACH|CFM)([0-9]+)$", name, flags=re.IGNORECASE
            )
            if not cm:
                continue
            if cm.group(2).upper() != target_kind:
                continue
            if int(float(cm.group(3))) != target_pressure:
                continue
            candidates.append((abs(float(cm.group(1)) - target_val), name))
        if candidates:
            matched_name = sorted(candidates, key=lambda x: x[0])[0][1]
            _log_approximation_warning_once(
                ("enclosure_air_leakage", matched_name),
                "Approximated enclosure_air_leakage value '%s' with nearest option '%s'.",
                raw_value,
                matched_name,
            )
            return matched_name

    m = re.match(r"^([0-9]*\.?[0-9]+)\s*(nACH|nCFM)$", normalized, flags=re.IGNORECASE)
    if m:
        target_val = float(m.group(1))
        target_kind = m.group(2).lower()
        candidates = []
        for name in option_names:
            cm = re.match(
                r"^([0-9]*\.?[0-9]+)\s*(nACH|nCFM)$", name, flags=re.IGNORECASE
            )
            if not cm:
                continue
            if cm.group(2).lower() != target_kind:
                continue
            candidates.append((abs(float(cm.group(1)) - target_val), name))
        if candidates:
            matched_name = sorted(candidates, key=lambda x: x[0])[0][1]
            _log_approximation_warning_once(
                ("enclosure_air_leakage", matched_name),
                "Approximated enclosure_air_leakage value '%s' with nearest option '%s'.",
                raw_value,
                matched_name,
            )
            return matched_name

    return None


def _match_option_by_numeric_properties(tsv_file_path, target_values, rows=None):
    """Match a TSV option row using one or more numeric property columns."""
    if rows is None:
        rows = get_tsv_data(tsv_file_path)

    best_name = None
    best_score = None
    best_row = None

    for row in rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue

        score = 0.0
        compared = 0
        for column_name, target_value in target_values.items():
            if target_value is None:
                continue
            compared += 1
            option_value = _to_optional_float(row.get(column_name))
            if option_value is None:
                score += 1e6
            else:
                score += abs(option_value - target_value)

        if compared == 0:
            continue

        if best_score is None or score < best_score:
            best_score = score
            best_name = option_name
            best_row = row

    if best_name is not None and best_score is not None and best_score > 1e-9:
        context_parts = []
        row_type = str(best_row.get("Type", "")).strip() if best_row is not None else ""
        if row_type != "":
            context_parts.append(row_type)
        if best_row is not None:
            for column_name in target_values:
                if column_name == "Type":
                    continue
                row_value = best_row.get(column_name)
                formatted_value = _format_number_token(row_value)
                if formatted_value is None:
                    formatted_value = str(row_value).strip()
                if formatted_value != "":
                    context_parts.append(formatted_value)
        context = " ".join(context_parts)
        if context != "":
            context = f" : {context}"
        target_values_block = _format_target_values_block(target_values)
        _log_approximation_warning_once(
            (
                Path(tsv_file_path).name,
                best_name,
            ),
            "Approximated %s option using nearest match '%s'%s\n  target values:\n%s",
            Path(tsv_file_path).name,
            best_name,
            context,
            target_values_block,
        )

    return best_name

def _update_numeric_enclosure_option(df, legacy_to_tsv_columns, tsv_filename, output_column, default_option):
    """Map a set of numeric legacy columns to a single option-string column."""
    if not any(column in df.columns for column in legacy_to_tsv_columns):
        return df

    tsv_path = _option_tsv_path(tsv_filename)

    for idx, row in df.iterrows():
        target_values = {}
        for legacy_column, tsv_column in legacy_to_tsv_columns.items():
            if legacy_column not in df.columns:
                continue
            numeric_value = _to_float(row.get(legacy_column))
            if numeric_value is not None:
                target_values[tsv_column] = numeric_value

        matched_name = _match_option_by_numeric_properties(tsv_path, target_values)
        if matched_name is None:
            matched_name = default_option
            _log_approximation_warning_once(
                ("numeric_default", output_column),
                f"No {output_column} mapping found at row {idx}; using default '{matched_name}'.",
            )

        df.at[idx, output_column] = matched_name

    return df


def _update_typed_numeric_enclosure_option(
    df,
    legacy_type_column,
    legacy_to_tsv_columns,
    tsv_filename,
    output_column,
    default_option,
    type_column_name="Type",
):
    """Map a legacy type column plus numeric columns to a single option-string column."""
    if not any(column in df.columns for column in legacy_to_tsv_columns) and legacy_type_column not in df.columns:
        return df

    tsv_path = _option_tsv_path(tsv_filename)
    rows = get_tsv_data(tsv_path)

    rows_by_type = {}
    for row in rows:
        option_name = str(row.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue
        type_key = _normalize_legacy_value(row.get(type_column_name))
        rows_by_type.setdefault(type_key, []).append(row)

    for idx, row in df.iterrows():
        target_values = {}
        for legacy_column, tsv_column in legacy_to_tsv_columns.items():
            if legacy_column not in df.columns:
                continue
            numeric_value = _to_float(row.get(legacy_column))
            if numeric_value is not None:
                target_values[tsv_column] = numeric_value

        candidate_rows = rows
        if legacy_type_column in df.columns:
            legacy_type = row.get(legacy_type_column)
            legacy_type_key = _normalize_legacy_value(legacy_type)
            typed_rows = rows_by_type.get(legacy_type_key)
            if typed_rows:
                candidate_rows = typed_rows

        matched_name = _match_option_by_numeric_properties(tsv_path, target_values, rows=candidate_rows)
        if matched_name is None:
            matched_name = default_option
            _log_approximation_warning_once(
                ("typed_numeric_default", output_column, legacy_type_column),
                f"No {output_column} mapping found at row {idx}; using default '{matched_name}'.",
            )

        df.at[idx, output_column] = matched_name

    return df


def build_enclosure_air_leakage_value(value, units, pressure):
    """Build the enclosure_air_leakage value from component columns."""
    if pd.isna(value) or pd.isna(units):
        return None

    value_str = str(value).strip()
    units_str = str(units).strip().lower()

    if "nach" in units_str or "natural" in units_str:
        return f"{value_str} nACH"

    if pd.notna(pressure):
        try:
            pressure_int = int(float(str(pressure).strip()))
            if "ach" in units_str:
                return f"{value_str} ACH{pressure_int}"
            if "cfm" in units_str:
                return f"{value_str} CFM{pressure_int}"
        except (ValueError, TypeError):
            return None

    return None


def _repo_root_from_script():
    """Return the project root that contains OpenStudio-HPXML and migration/."""
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent.parent.parent,
        script_dir.parent.parent,
    ]

    for root in candidates:
        candidate = (
            root
            / "OpenStudio-HPXML"
            / "BuildResidentialHPXML"
            / "resources"
            / "options"
        )
        if candidate.exists():
            return root
    return script_dir.parent


def _option_tsv_path(filename):
    """Resolve a TSV path relative to the repository root."""
    root = _repo_root_from_script()
    return (
        root
        / "OpenStudio-HPXML"
        / "BuildResidentialHPXML"
        / "resources"
        / "options"
        / filename
    )


def _normalize_legacy_value(value):
    """Normalize legacy choice values into a stable comparable key."""
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _value_or_legacy_alias(raw_value, aliases, option_names_lower):
    """Resolve a legacy value into a canonical v1.12 option name when possible."""
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if text == "":
        return None

    direct = option_names_lower.get(text.lower())
    if direct is not None:
        return direct

    key = _normalize_legacy_value(text)
    return aliases.get(key)


def _to_optional_float(value):
    """Convert a value to float when possible, otherwise return None."""
    if value is None:
        return None
    sval = str(value).strip()
    if sval == "" or sval.lower() == "nan":
        return None
    try:
        return float(sval)
    except (TypeError, ValueError):
        return None


def _to_bool(value, default=False):
    """Convert common boolean-like values from legacy CSV fields."""
    if value is None:
        return default
    sval = str(value).strip().lower()
    if sval in {"true", "1", "yes", "y", "oui"}:
        return True
    if sval in {"false", "0", "no", "n", "non"}:
        return False
    return default


def _to_float(value):
    """Convert a value to float when possible, otherwise return None."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_heater_type(value):
    """Normalize heater type values to v1.12 canonical tokens."""
    key = _normalize_legacy_value(value)
    aliases = {
        "": "not present",
        "none": "not present",
        "notpresent": "not present",
        "electricresistance": "electric resistance",
        "electric": "electric resistance",
        "heatpump": "heat pump",
        "gasfired": "gas fired",
        "naturalgas": "gas fired",
        "gas": "gas fired",
    }
    return aliases.get(key, str(value).strip().lower())


def _nearest_allowed_multiplier(value):
    """Map arbitrary multipliers to supported discrete option multipliers."""
    allowed = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0]
    if value is None:
        return 1.0
    matched = min(allowed, key=lambda x: abs(x - value))
    if abs(matched - value) > 1e-9:
        logger.warning(
            "Approximated multiplier %s to nearest allowed value %s.",
            value,
            matched,
        )
    return matched


def _format_percent_from_multiplier(multiplier):
    pct = int(round(multiplier * 100))
    return f"{pct}% Usage"


def _build_misc_option_from_legacy(
    row,
    present_col,
    pump_annual_col,
    pump_multiplier_col,
    heater_type_col,
    heater_annual_kwh_col,
    heater_annual_therm_col,
    heater_multiplier_col,
    tsv_rows,
):
    """Convert legacy pool/spa columns from one row into a v1.12 misc option name."""
    present = _to_bool(row.get(present_col), default=False)
    if not present:
        return "None"

    heater_type = _normalize_heater_type(row.get(heater_type_col))
    pump_annual = _to_optional_float(row.get(pump_annual_col))
    heater_annual_kwh = _to_optional_float(row.get(heater_annual_kwh_col))
    heater_annual_therm = _to_optional_float(row.get(heater_annual_therm_col))
    pump_multiplier = _to_optional_float(row.get(pump_multiplier_col))
    heater_multiplier = _to_optional_float(row.get(heater_multiplier_col))

    def _row_float(r, key):
        return _to_optional_float(r.get(key))

    matches = []
    for opt in tsv_rows:
        option_name = str(opt.get("Option Name", "")).strip()
        if option_name == "" or option_name.startswith("#"):
            continue

        opt_heater = _normalize_heater_type(opt.get("Heater Type", ""))
        if heater_type != "" and opt_heater != heater_type:
            continue

        ok = True
        compared = 0
        for legacy_value, tsv_key in [
            (pump_annual, "Pump Annual Energy Use [kWh/yr]"),
            (pump_multiplier, "Pump Usage Multiplier"),
            (heater_annual_kwh, "Heater Annual Electricity Use [kWh/yr]"),
            (heater_annual_therm, "Heater Annual Natural Gas Use [kWh/yr]"),
            (heater_multiplier, "Heater Usage Multiplier"),
        ]:
            if legacy_value is None:
                continue
            compared += 1
            opt_val = _row_float(opt, tsv_key)
            if opt_val is None or abs(opt_val - legacy_value) > 1e-6:
                ok = False
                break
        if ok:
            matches.append((compared, option_name))

    if len(matches) > 0:
        matches.sort(key=lambda x: x[0], reverse=True)
        return matches[0][1]

    if heater_type == "not present":
        usage_multiplier = _nearest_allowed_multiplier(pump_multiplier)
        return f"Unheated, {_format_percent_from_multiplier(usage_multiplier)}"

    heater_label_by_type = {
        "electric resistance": "Electric Resistance Heater",
        "heat pump": "Heat Pump Heater",
        "gas fired": "Natural Gas Heater",
    }
    heater_label = heater_label_by_type.get(heater_type)
    if heater_label is None:
        logger.warning(
            f"Unknown heater type '{row.get(heater_type_col)}'; using unheated pool/spa option."
        )
        usage_multiplier = _nearest_allowed_multiplier(pump_multiplier)
        return f"Unheated, {_format_percent_from_multiplier(usage_multiplier)}"

    usage_multiplier = _nearest_allowed_multiplier(heater_multiplier)
    return f"{heater_label}, {_format_percent_from_multiplier(usage_multiplier)}"


def _legacy_overhang_cols(prefix=""):
    """Return legacy enclosure overhang column mapping for a given prefix."""
    return {
        "front_depth": f"{prefix}overhangs_front_depth",
        "back_depth": f"{prefix}overhangs_back_depth",
        "left_depth": f"{prefix}overhangs_left_depth",
        "right_depth": f"{prefix}overhangs_right_depth",
        "front_top": f"{prefix}overhangs_front_distance_to_top_of_window",
        "back_top": f"{prefix}overhangs_back_distance_to_top_of_window",
        "left_top": f"{prefix}overhangs_left_distance_to_top_of_window",
        "right_top": f"{prefix}overhangs_right_distance_to_top_of_window",
        "front_bottom": f"{prefix}overhangs_front_distance_to_bottom_of_window",
        "back_bottom": f"{prefix}overhangs_back_distance_to_bottom_of_window",
        "left_bottom": f"{prefix}overhangs_left_distance_to_bottom_of_window",
        "right_bottom": f"{prefix}overhangs_right_distance_to_bottom_of_window",
    }


def _normalize_duct_leakage_units(units):
    """Normalize legacy duct leakage units to v1.12 tokens."""
    if units is None:
        return None
    key = _normalize_legacy_value(units)
    aliases = {
        "percent": "Percent",
        "%": "Percent",
        "cfm25": "CFM25",
        "cfm50": "CFM50",
        "cfm25per100ft2": "CFM25 per 100ft2",
        "cfm50per100ft2": "CFM50 per 100ft2",
    }
    return aliases.get(key)


def _normalize_percent_value(value):
    """Normalize a leakage percentage that may be expressed as fraction or percent."""
    fval = _to_optional_float(value)
    if fval is None:
        return None
    return fval / 100.0 if fval > 1.0 else fval
