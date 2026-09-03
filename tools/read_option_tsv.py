"""Utilities to read OpenStudio-HPXML option TSV files.

Inspired by BuildResidentialHPXML/resources/options.rb:
- Read TSV data once and cache it
- Infer/convert basic datatypes per column (integer, float, boolean, string)
- Expose generic helpers to retrieve option names and row properties
"""

import csv
from pathlib import Path


_TSV_CACHE = {}


def _is_comment_row(row):
    option_name = row.get("Option Name")
    if option_name is None:
        return False
    option_name = str(option_name).strip()
    return option_name.startswith("#")


def _infer_column_type(values):
    # Mirrors options.rb behavior:
    # mixed integer/float -> float, mixed other types -> string.
    kinds = set()
    for value in values:
        s = str(value).strip()
        if s == "":
            continue

        try:
            f = float(s)
            kinds.add("integer" if f.is_integer() else "float")
            continue
        except ValueError:
            pass

        if s.upper() in {"TRUE", "FALSE"}:
            kinds.add("boolean")
        else:
            kinds.add("string")

    if kinds == {"integer", "float"}:
        return "float"
    if len(kinds) != 1:
        return "string"
    return next(iter(kinds)) if kinds else "string"


def _convert_value(value, dtype):
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return ""

    if dtype == "integer":
        return int(float(s))
    if dtype == "float":
        return float(s)
    if dtype == "boolean":
        return s.upper() == "TRUE"
    return s


def get_tsv_data(tsv_file_path):
    """Read a TSV file and return typed rows (cached).

    Args:
        tsv_file_path (str | Path): Absolute or relative path to TSV file.

    Returns:
        list[dict]: List of rows with values converted to inferred types.
    """
    tsv_path = str(Path(tsv_file_path).resolve())
    if tsv_path in _TSV_CACHE:
        return _TSV_CACHE[tsv_path]

    with open(tsv_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        rows = [dict(row) for row in reader]

    headers = list(rows[0].keys()) if rows else []

    column_types = {}
    for header in headers:
        values = [row.get(header, "") for row in rows if not _is_comment_row(row)]
        column_types[header] = _infer_column_type(values)

    for row in rows:
        for header in headers:
            row[header] = _convert_value(row.get(header, ""), column_types[header])

    _TSV_CACHE[tsv_path] = rows
    return rows


def get_option_names(tsv_file_path):
    """Return all valid option names from a TSV file."""
    option_names = []
    for row in get_tsv_data(tsv_file_path):
        option_name = row.get("Option Name")
        if option_name is None:
            continue
        option_name = str(option_name).strip()
        if option_name == "" or option_name.startswith("#"):
            continue
        option_names.append(option_name)
    return option_names


def get_property_names(tsv_file_path):
    """Return non-option column names with units stripped from headers."""
    rows = get_tsv_data(tsv_file_path)
    if not rows:
        return []

    property_names = []
    for header in rows[0].keys():
        if header == "Option Name":
            continue
        clean = str(header)
        if "[" in clean:
            clean = clean.split("[", 1)[0].strip()
        property_names.append(clean)
    return property_names


def get_property_units(tsv_file_path):
    """Return units parsed from headers, aligned with get_property_names()."""
    rows = get_tsv_data(tsv_file_path)
    if not rows:
        return []

    units = []
    for header in rows[0].keys():
        if header == "Option Name":
            continue
        text = str(header)
        if "[" in text and "]" in text:
            units.append(text.split("[", 1)[1].split("]", 1)[0].strip())
        else:
            units.append("")
    return units


def get_option_properties(tsv_file_path, option_name):
    """Return detailed properties for a given option name.

    Args:
        tsv_file_path (str | Path): Option TSV file path.
        option_name (str): Option Name to look up.

    Returns:
        dict: Property map (columns except Option Name) for matched option.

    Raises:
        ValueError: If option is not found.
    """
    if option_name is None:
        return {}

    for row in get_tsv_data(tsv_file_path):
        current = row.get("Option Name")
        if current == option_name:
            props = {}
            for key, value in row.items():
                if key == "Option Name":
                    continue
                clean = str(key)
                if "[" in clean:
                    clean = clean.split("[", 1)[0].strip()
                props[clean] = value
            return props

    raise ValueError(f"Could not find option '{option_name}' in TSV '{tsv_file_path}'.")