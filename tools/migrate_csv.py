"""
Migrate old CSV files to the new format. from HPXML 4.1 to 5.0
This script is used to convert CSV files that were created with an older version of the simulator to the new format 
that is compatible with the current version.
"""

import pandas as pd
import argparse
import os
from pathlib import Path

def update_column_value(df, column_name, old_value, new_value):
    """
    Update the value of a specific column in a DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame to update.
        column_name (str): The name of the column to update.
        old_value (str): The value to be replaced.
        new_value (str): The new value to replace the old value.
        
    Returns:
        pd.DataFrame: The updated DataFrame.
    """    
    # Skip if column doesn't exist
    if column_name not in df.columns:
        return df
    
    # Update the specified column with the new value
    df[column_name] = df[column_name].replace(old_value, new_value)
    return df


def update_v110_to_v112(input_filePath, output_filePath):
    """
    Update the CSV file from version 1.10 to version 1.12.
    Replaces "none" with "not present" in 5 HPXML fields.

    Args:
        input_filePath (str): The path to the input CSV file.
        output_filePath (str): The path to the output CSV file.
    """   
    # Load CSV once
    df = pd.read_csv(input_filePath, dtype=str, keep_default_na=False)
    
    # Apply all replacements to the same DataFrame
    columns_to_update = [
        'wall_siding_type',
        'window_interior_shading_type',
        'window_exterior_shading_type',
        'pool_heater_type',
        'permanent_spa_heater_type'
    ]
    
    for column in columns_to_update:
        df = update_column_value(df, column, 'none', 'not present')
    
    # Write output once
    df.to_csv(output_filePath, index=False)
    
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

 
