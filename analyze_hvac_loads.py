#!/usr/bin/env python3
"""
Script to analyze HVAC heating loads from simulation results.

This script reads the simulation results metadata and timeseries data
and extracts heating variables for electricity and natural gas.
"""

import os
import pandas as pd
import json
from pathlib import Path


def load_metadata(results_dir: str = "results") -> pd.DataFrame:
    """
    Load metadata from parquet dataset.
    
    Args:
        results_dir: Path to results directory
        
    Returns:
        DataFrame with metadata
    """
    metadata_path = os.path.join(results_dir, "metadata.parquet")
    if os.path.exists(metadata_path):
        metadata = pd.read_parquet(metadata_path)
        print(f"Loaded metadata: {metadata.shape[0]} rows, {metadata.shape[1]} columns")
        return metadata
    else:
        print(f"Metadata directory not found: {metadata_path}")
        return pd.DataFrame()


def load_timeseries(results_dir: str = "results") -> pd.DataFrame:
    """
    Load timeseries data from parquet dataset.
    
    Args:
        results_dir: Path to results directory
        
    Returns:
        DataFrame with timeseries data
    """
    timeseries_path = os.path.join(results_dir, "timeseries.parquet")
    if os.path.exists(timeseries_path):
        timeseries = pd.read_parquet(timeseries_path)
        print(f"Loaded timeseries: {timeseries.shape[0]} rows, {timeseries.shape[1]} columns")
        return timeseries
    else:
        print(f"Timeseries directory not found: {timeseries_path}")
        return pd.DataFrame()


def extract_heating_variables(timeseries: pd.DataFrame) -> dict:
    """
    Extract heating variables from timeseries data.
    
    Retrieves:
    - End Use: Electricity: Heating
    - End Use: Natural Gas: Heating
    
    Args:
        timeseries: DataFrame with timeseries data
        
    Returns:
        Dictionary with heating variables indexed by building_id
    """
    heating_vars = {}
    
    # List of columns to look for
    electricity_heating_cols = [
        col for col in timeseries.columns 
        if "heating" in col.lower() and "electricity" in col.lower()
    ]
    
    natural_gas_heating_cols = [
        col for col in timeseries.columns 
        if "heating" in col.lower() and ("natural gas" in col.lower() or "gas" in col.lower())
    ]
    
    print(f"\nFound {len(electricity_heating_cols)} electricity heating columns:")
    for col in electricity_heating_cols:
        print(f"  - {col}")
    
    print(f"\nFound {len(natural_gas_heating_cols)} natural gas heating columns:")
    for col in natural_gas_heating_cols:
        print(f"  - {col}")
    
    # Group by building_id and aggregate heating data
    if "building_id" in timeseries.columns:
        for building_id in timeseries["building_id"].unique():
            building_data = timeseries[timeseries["building_id"] == building_id]
            
            heating_vars[building_id] = {
                "electricity_heating": {},
                "natural_gas_heating": {}
            }
            
            # Aggregate electricity heating
            for col in electricity_heating_cols:
                if col in building_data.columns:
                    heating_vars[building_id]["electricity_heating"][col] = {
                        "total": building_data[col].sum(),
                        "mean": building_data[col].mean(),
                        "max": building_data[col].max(),
                        "min": building_data[col].min(),
                    }
            
            # Aggregate natural gas heating
            for col in natural_gas_heating_cols:
                if col in building_data.columns:
                    heating_vars[building_id]["natural_gas_heating"][col] = {
                        "total": building_data[col].sum(),
                        "mean": building_data[col].mean(),
                        "max": building_data[col].max(),
                        "min": building_data[col].min(),
                    }
    
    return heating_vars


def print_heating_summary(heating_vars: dict):
    """
    Print summary of heating variables.
    
    Args:
        heating_vars: Dictionary with heating variables
    """
    print("\n" + "="*80)
    print("HVAC HEATING LOADS SUMMARY")
    print("="*80)
    
    for building_id, data in heating_vars.items():
        print(f"\n--- Building ID: {building_id} ---")
        
        # Electricity heating
        if data["electricity_heating"]:
            print(f"\nElectricity Heating:")
            for var_name, stats in data["electricity_heating"].items():
                print(f"  {var_name}:")
                print(f"    Total: {stats['total']:.2f}")
                print(f"    Mean:  {stats['mean']:.2f}")
                print(f"    Max:   {stats['max']:.2f}")
                print(f"    Min:   {stats['min']:.2f}")
        else:
            print("\nElectricity Heating: No data found")
        
        # Natural gas heating
        if data["natural_gas_heating"]:
            print(f"\nNatural Gas Heating:")
            for var_name, stats in data["natural_gas_heating"].items():
                print(f"  {var_name}:")
                print(f"    Total: {stats['total']:.2f}")
                print(f"    Mean:  {stats['mean']:.2f}")
                print(f"    Max:   {stats['max']:.2f}")
                print(f"    Min:   {stats['min']:.2f}")
        else:
            print("\nNatural Gas Heating: No data found")


def save_heating_summary(heating_vars: dict, output_file: str = "hvac_heating_summary.json"):
    """
    Save heating summary to JSON file.
    
    Args:
        heating_vars: Dictionary with heating variables
        output_file: Output file path
    """
    with open(output_file, "w") as f:
        json.dump(heating_vars, f, indent=2)
    print(f"\nHeating summary saved to: {output_file}")


def main(results_dir: str = "results"):
    """
    Main function to analyze HVAC heating loads.
    
    Args:
        results_dir: Path to results directory
    """
    print("Analyzing HVAC Heating Loads")
    print("="*80)
    
    # Load data
    metadata = load_metadata(results_dir)
    timeseries = load_timeseries(results_dir)
    
    if timeseries.empty:
        print("Error: Could not load timeseries data")
        return
    
    # Print available columns
    print(f"\nAvailable timeseries columns ({len(timeseries.columns)}):")
    for col in sorted(timeseries.columns):
        print(f"  - {col}")
    
    # Extract heating variables
    heating_vars = extract_heating_variables(timeseries)
    
    # Print summary
    print_heating_summary(heating_vars)
    
    # Save summary
    save_heating_summary(heating_vars)


if __name__ == "__main__":
    import sys
    
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    main(results_dir)
