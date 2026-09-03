"""
Migrate old CSV files to the new format. from HPXML 4.1 to 5.0
This script is used to convert CSV files that were created with an older version of the simulator to the new format 
that is compatible with the current version.
"""

import pandas as pd
import argparse
import os
from pathlib import Path

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
    
    # Create enclosure_air_leakage column
    df['enclosure_air_leakage'] = df.apply(
        lambda row: build_enclosure_air_leakage_value(
            row['air_leakage_value'],
            row['air_leakage_units'],
            row['air_leakage_house_pressure']
        ),
        axis=1
    )

    # remove the old required_cols
    df.drop(columns=required_cols, inplace=True)
    
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

 
