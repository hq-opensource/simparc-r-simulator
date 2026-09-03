"""
Migrate old CSV files to the new format. from HPXML 4.1 to 5.0
This script is used to convert CSV files that were created with an older version of the simulator to the new format 
that is compatible with the current version.
"""

import pandas as pd
import argparse
import os
import logging
import re
from pathlib import Path
from read_option_tsv import get_tsv_data, get_option_names


logger = logging.getLogger(__name__)


def _build_geometry_unit_lookup(tsv_file_path):
    """Build a map of (facility_type_lower, stories_int) -> option name."""
    choices = {}
    for row in get_tsv_data(tsv_file_path):
        option_name = str(row.get('Option Name', '')).strip()
        if option_name == '' or option_name.startswith('#'):
            continue

        facility_type = str(row.get('Facility Type', '')).strip().lower()
        stories = row.get('Number of Stories', '')
        if facility_type == '' or stories == '':
            continue

        try:
            stories_int = int(float(str(stories)))
        except (ValueError, TypeError):
            continue

        choices[(facility_type, stories_int)] = option_name
    return choices


def _format_number_token(value):
    """
        Format a numeric token to a string, removing unnecessary decimal points for integers.
    """
    try:
        fval = float(str(value).strip())
    except (ValueError, TypeError):
        return None
    if fval.is_integer():
        return str(int(fval))
    return f"{fval:.12g}"


def _normalize_enclosure_value(text):
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
    normalized = _normalize_enclosure_value(raw_value)
    lookup = {name.lower(): name for name in option_names}
    direct = lookup.get(normalized.lower())
    if direct is not None:
        return direct

    # Numeric fallback: pick nearest option with same unit flavor.
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*(ACH|CFM)([0-9]+)$", normalized, flags=re.IGNORECASE)
    if m:
        target_val = float(m.group(1))
        target_kind = m.group(2).upper()
        target_pressure = int(float(m.group(3)))
        candidates = []
        for name in option_names:
            cm = re.match(r"^([0-9]*\.?[0-9]+)\s*(ACH|CFM)([0-9]+)$", name, flags=re.IGNORECASE)
            if not cm:
                continue
            if cm.group(2).upper() != target_kind:
                continue
            if int(float(cm.group(3))) != target_pressure:
                continue
            candidates.append((abs(float(cm.group(1)) - target_val), name))
        if candidates:
            return sorted(candidates, key=lambda x: x[0])[0][1]

    m = re.match(r"^([0-9]*\.?[0-9]+)\s*(nACH|nCFM)$", normalized, flags=re.IGNORECASE)
    if m:
        target_val = float(m.group(1))
        target_kind = m.group(2).lower()
        candidates = []
        for name in option_names:
            cm = re.match(r"^([0-9]*\.?[0-9]+)\s*(nACH|nCFM)$", name, flags=re.IGNORECASE)
            if not cm:
                continue
            if cm.group(2).lower() != target_kind:
                continue
            candidates.append((abs(float(cm.group(1)) - target_val), name))
        if candidates:
            return sorted(candidates, key=lambda x: x[0])[0][1]

    return None

def update_column_values_v110_to_v112(df):
    """
    Replace "none" with "not present" in v1.10→v1.12 migration.

    Args:
        df (pd.DataFrame): The DataFrame to update.
        
    Returns:
        pd.DataFrame: The updated DataFrame.
    """      
    columns_to_update = [
        'wall_siding_type',
        'window_interior_shading_type',
        'window_exterior_shading_type',
        'pool_heater_type',
        'permanent_spa_heater_type'
    ]
    
    for column in columns_to_update:
        # Skip if column doesn't exist
        if column not in df.columns:
            continue
        # Update the specified column with the new value
        df[column] = df[column].replace('none', 'not present')
    
    return df

def build_enclosure_air_leakage_value(value, units, pressure):
    """
    Build the enclosure_air_leakage value from component columns.
    
    Format examples from TSV:
    - "1 ACH50"  (ACH with pressure)
    - "0.2 nACH" (natural ACH, no pressure)
    - "1080 CFM50" (CFM with pressure)
    
    Args:
        value (str/float): Air leakage numeric value
        units (str): Units type (ACH, CFM, nACH, etc.)
        pressure (str/int): House pressure (50, 45, etc.)
        
    Returns:
        str: Formatted enclosure_air_leakage value, or None if inputs invalid
    """
    if pd.isna(value) or pd.isna(units):
        return None
    
    # Convert to strings and normalize
    value_str = str(value).strip()
    units_str = str(units).strip().lower()
    
    # Natural ACH (nACH/ACHnatural) doesn't require pressure
    if 'nach' in units_str or 'natural' in units_str:
        return f"{value_str} nACH"
    
    # ACH and CFM require pressure
    if pd.notna(pressure):
        try:
            pressure_int = int(float(str(pressure).strip()))
            if 'ach' in units_str:
                return f"{value_str} ACH{pressure_int}"
            elif 'cfm' in units_str:
                return f"{value_str} CFM{pressure_int}"
        except (ValueError, TypeError):
            return None
    
    return None


def update_leakage_column_value(df):
    """
    Create the enclosure_air_leakage column from v1.10 air leakage component columns.

    Args:
        df (pd.DataFrame): The DataFrame to update.

    Returns:
        pd.DataFrame: The updated DataFrame with enclosure_air_leakage column.
    """    
    # Check if required columns exist
    required_cols = ['air_leakage_value', 'air_leakage_units', 'air_leakage_house_pressure']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        print(f"Warning: Missing columns {missing_cols}. Skipping enclosure_air_leakage creation.")
        return df
    
    new_air_leakage_values = []
    for idx, row in df.iterrows():
        value = row['air_leakage_value']
        units = row['air_leakage_units']
        pressure = row['air_leakage_house_pressure']
        
        new_value = build_enclosure_air_leakage_value(value, units, pressure)
        new_air_leakage_values.append(new_value)

    # Normalize to canonical option names when available.
    tsv_path = Path(__file__).resolve().parents[1] / 'OpenStudio-HPXML' / 'BuildResidentialHPXML' / 'resources' / 'options' / 'enclosure_air_leakage.tsv'
    option_names = get_option_names(str(tsv_path))
    
    # find closest match for each new value
    for i, new_value in enumerate(new_air_leakage_values):
        if new_value is None:
            continue
        canonical = _match_enclosure_option(new_value, option_names)
        if canonical is not None:
            new_air_leakage_values[i] = canonical
        else:
            logger.warning(f"No matching option found for enclosure_air_leakage value '{new_value}'. Setting to None.")
            new_air_leakage_values[i] = None
    df['enclosure_air_leakage'] = new_air_leakage_values

    # remove the old required_cols
    df.drop(columns=required_cols, inplace=True)
    
    return df

def update_geomtry_unit_v110_to_v112(df):
    """
    Update the geometry_unit column from v1.10→v1.12 migration.
    
    Args:
        df (pd.DataFrame): The DataFrame to update.
    Returns:
        pd.DataFrame: The updated DataFrame.
    """
    # Get option names from geometry_unit_type TSV.
    tsv_path = Path(__file__).resolve().parents[1] / 'OpenStudio-HPXML' / 'BuildResidentialHPXML' / 'resources' / 'options' / 'geometry_unit_type.tsv'
    geometry_unit_choices = _build_geometry_unit_lookup(str(tsv_path))
    option_names = get_option_names(str(tsv_path))
    option_names_lower = {name.lower(): name for name in option_names}

    aliases = {
        'single family detached': 'single-family detached',
        'single-family detached': 'single-family detached',
        'single family attached': 'single-family attached',
        'single-family attached': 'single-family attached',
        'apartment': 'apartment unit',
        'apartment unit': 'apartment unit',
        'manufactured home': 'manufactured home',
    }
    
    if 'geometry_unit_type' not in df.columns or 'geometry_unit_num_floors_above_grade' not in df.columns:
        print("Warning: Missing column 'geometry_unit_type' or 'geometry_unit_num_floors_above_grade'. Skipping geometry_unit update.")
        return df

    # Map legacy values into the option-based format expected by v1.12.
    for idx, row in df.iterrows():
        old_value_unit = str(row['geometry_unit_type']).strip()
        old_value_floor = row['geometry_unit_num_floors_above_grade']

        # 1) Already in option format -> normalize case to canonical option text.
        existing = option_names_lower.get(old_value_unit.lower())
        if existing is not None:
            df.at[idx, 'geometry_unit_type'] = existing
            continue

        # 2) Legacy format (e.g., "apartment unit") -> map with number of stories.
        facility_key = aliases.get(old_value_unit.lower(), old_value_unit.lower())
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

        df.at[idx, 'geometry_unit_type'] = mapped

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
    df = update_leakage_column_value(df)

    # Update geometry_unit column from v1.10→v1.12 migration
    df = update_geomtry_unit_v110_to_v112(df)
    
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
        raise ValueError("Output file path must be different from input file path to avoid overwriting the original file.")
    
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
            """
    )
    
    parser.add_argument(
        "input",
        metavar="INPUT_FILE",
        help="Path to input CSV file (required)"
    )
    
    parser.add_argument(
        "output",
        metavar="OUTPUT_FILE",
        nargs="?",
        default=None,
        help="Path to output CSV file (optional; default: INPUT_FILE-1.12.csv in v1.12/ subdirectory)"
    )
    
    args = parser.parse_args()
    
    try:
        main(args.input, args.output)
    except Exception as e:
        print(f"✗ Error: {e}")
        exit(1)   

 
