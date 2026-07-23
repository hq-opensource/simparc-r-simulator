#!/usr/bin/env python3
"""
Script to analyze HVAC heating loads from simulation results.

This script reads the simulation results metadata and timeseries data
and extracts heating variables for electricity and natural gas.
"""

import os
import math
import pandas as pd
import json
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "generated" / "hvac_analysis"


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
    Load timeseries data by reading each building partition separately, then
    concatenating. This preserves columns that only exist for some buildings
    (e.g. natural gas heating only for buildings with a gas system).
    
    Args:
        results_dir: Path to results directory
        
    Returns:
        DataFrame with timeseries data
    """
    timeseries_path = os.path.join(results_dir, "timeseries.parquet")
    if not os.path.exists(timeseries_path):
        print(f"Timeseries directory not found: {timeseries_path}")
        return pd.DataFrame()

    partitions = sorted(Path(timeseries_path).glob("building_id=*"))
    if not partitions:
        print(f"No building partitions found in {timeseries_path}")
        return pd.DataFrame()

    dfs = []
    for partition in partitions:
        building_id = int(partition.name.split("=")[1])
        df = pd.read_parquet(partition)
        df["building_id"] = building_id
        dfs.append(df)

    # Concatenate with outer join so all columns are preserved across buildings
    timeseries = pd.concat(dfs, axis=0, join="outer", ignore_index=True)
    print(f"Loaded timeseries: {timeseries.shape[0]} rows, {timeseries.shape[1]} columns (from {len(dfs)} buildings)")
    return timeseries


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


def extract_annual_heating_from_metadata(metadata: pd.DataFrame) -> pd.DataFrame:
    """
    Extract annual heating values from metadata for all fuel types.

    Args:
        metadata: DataFrame with metadata

    Returns:
        DataFrame with building_id and annual heating columns
    """
    heating_cols = [
        col for col in metadata.columns
        if "heating" in col.lower() and col.startswith("End Use:")
    ]

    if "building_id" not in metadata.columns:
        print("No building_id column in metadata")
        return pd.DataFrame()

    result = metadata[["building_id"] + heating_cols].copy()
    return result


def _subplot_grid(n_plots: int, max_cols: int = 3) -> tuple[int, int]:
    """
    Compute a compact subplot grid for n_plots.
    """
    cols = min(max_cols, max(1, n_plots))
    rows = math.ceil(n_plots / cols)
    return rows, cols


def plot_heating_timeseries(timeseries: pd.DataFrame, output_file: str = "hvac_heating_timeseries.png"):
    """
    Plot electricity and natural gas heating timeseries for each building.

    Args:
        timeseries: DataFrame with timeseries data (all buildings)
        output_file: Output PNG file path
    """
    elec_col = next((c for c in timeseries.columns if c == "End Use: Electricity: Heating_kWh"), None)
    gas_col  = next((c for c in timeseries.columns if c == "End Use: Natural Gas: Heating_kBtu"), None)
    time_col = next((c for c in timeseries.columns if c == "Time"), None)

    if not elec_col and not gas_col:
        print("No heating columns found for plotting")
        return

    building_ids = sorted(timeseries["building_id"].unique())
    n = len(building_ids)

    if n == 0:
        print("No buildings found in timeseries; skipping timeseries plot")
        return

    rows, cols = _subplot_grid(n)
    fig, axes = plt.subplots(rows, cols, figsize=(7 * cols, 3.8 * rows), sharex=False)
    axes = np.array(axes).reshape(-1)

    legend_handles = []
    if elec_col:
        legend_handles.append(mlines.Line2D([], [], color="royalblue", linewidth=1, label="Electricity Heating (kWh)"))
    if gas_col:
        legend_handles.append(mlines.Line2D([], [], color="firebrick", linewidth=1, label="Natural Gas Heating (kWh)"))

    kbtu_to_kwh = 0.293071
    for i, bid in enumerate(building_ids):
        ax = axes[i]
        df = timeseries[timeseries["building_id"] == bid].sort_values(time_col or timeseries.columns[0])
        x = df[time_col] if time_col else df.index

        if elec_col:
            ax.plot(x, df[elec_col].fillna(0), color="royalblue", linewidth=0.8)
        if gas_col:
            ax.plot(x, df[gas_col].fillna(0) * kbtu_to_kwh, color="firebrick", linewidth=0.8)

        ax.set_title(f"Building {bid}")
        ax.set_ylabel("Energy (kWh)")
        ax.tick_params(axis="x", rotation=30)

    for ax in axes[n:]:
        ax.set_visible(False)

    if legend_handles:
        fig.legend(handles=legend_handles, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0))

    fig.suptitle("HVAC Heating Loads — Electricity vs Natural Gas", y=1.02, fontsize=13)
    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nHeating timeseries plot saved to: {output_file}")


def _fit_prism_model(daily_df: pd.DataFrame, temp_col: str, total_col: str) -> dict:
    """
    Fit a simple PRISM-style heating model:
    y = a + b * max(0, T_balance - T_outdoor)

    Returns best-fit parameters and prediction series.
    """
    t = daily_df[temp_col].to_numpy(dtype=float)
    y = daily_df[total_col].to_numpy(dtype=float)

    valid = np.isfinite(t) & np.isfinite(y)
    t = t[valid]
    y = y[valid]

    if len(t) < 10:
        return {
            "t_balance": np.nan,
            "intercept": np.nan,
            "slope": np.nan,
            "r2": np.nan,
            "pred": np.full_like(t, np.nan, dtype=float),
            "temp": t,
        }

    best = {"sse": np.inf}
    for t_balance in np.arange(-25.0, 26.0, 0.5):
        x = np.maximum(0.0, t_balance - t)
        X = np.column_stack([np.ones_like(x), x])
        coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ coef
        sse = np.sum((y - pred) ** 2)

        if sse < best["sse"]:
            best = {
                "sse": sse,
                "t_balance": t_balance,
                "intercept": float(coef[0]),
                "slope": float(coef[1]),
                "pred": pred,
                "temp": t,
                "y": y,
            }

    y_mean = np.mean(best["y"])
    sst = np.sum((best["y"] - y_mean) ** 2)
    r2 = np.nan if sst <= 0 else 1.0 - best["sse"] / sst
    best["r2"] = float(r2)
    return best


def plot_prism_heating_signature(timeseries: pd.DataFrame, output_file: str = "hvac_heating_prism.png"):
    """
    Create PRISM-style energy-vs-outdoor-temperature plots per building.

    Shows daily energy by outdoor drybulb for:
    - Electricity heating
    - Natural gas heating (converted to kWh)
    - Total heating energy
    - PRISM fitted heat-load curve
    """
    temp_col = next((c for c in ["Weather: Drybulb Temperature_C", "Weather: Drybulb Temperature_F"] if c in timeseries.columns), None)
    if temp_col is None:
        print("No outdoor drybulb temperature column found; skipping PRISM plot")
        return

    elec_col = next((c for c in timeseries.columns if c == "End Use: Electricity: Heating_kWh"), None)
    gas_col = next((c for c in timeseries.columns if c == "End Use: Natural Gas: Heating_kBtu"), None)
    time_col = next((c for c in timeseries.columns if c in ["Time", "TimeUTC"]), None)

    if time_col is None:
        print("No time column found; skipping PRISM plot")
        return

    if elec_col is None and gas_col is None:
        print("No heating columns found for PRISM plot")
        return

    working = timeseries.copy()
    working[time_col] = pd.to_datetime(working[time_col], errors="coerce")
    working = working.dropna(subset=[time_col])

    if temp_col.endswith("_F"):
        temp_c = (working[temp_col].astype(float) - 32.0) * 5.0 / 9.0
    else:
        temp_c = working[temp_col].astype(float)

    working["outdoor_temp_c"] = temp_c
    working["elec_heating_kwh"] = working[elec_col].fillna(0.0) if elec_col else 0.0
    gas_kwh = working[gas_col].fillna(0.0) * 0.293071 if gas_col else 0.0
    working["gas_heating_kwh"] = gas_kwh
    working["total_heating_kwh"] = working["elec_heating_kwh"] + working["gas_heating_kwh"]
    working["date"] = working[time_col].dt.date

    building_ids = sorted(working["building_id"].unique())
    n = len(building_ids)

    if n == 0:
        print("No buildings found in timeseries; skipping PRISM plot")
        return

    rows, cols = _subplot_grid(n)
    fig, axes = plt.subplots(rows, cols, figsize=(6.2 * cols, 4.8 * rows))
    axes = np.array(axes).reshape(-1)

    legend_handles = [
        mlines.Line2D([], [], color="royalblue", marker="o", markersize=4, linestyle="None", alpha=0.6, label="Electricity Heating"),
        mlines.Line2D([], [], color="firebrick", marker="o", markersize=4, linestyle="None", alpha=0.6, label="Natural Gas Heating"),
        mlines.Line2D([], [], color="darkgreen", marker="o", markersize=4, linestyle="None", alpha=0.6, label="Total Heating"),
        mlines.Line2D([], [], color="black", linewidth=2, label="PRISM fit"),
    ]

    for i, bid in enumerate(building_ids):
        ax = axes[i]
        bdf = working[working["building_id"] == bid]

        daily = (
            bdf.groupby("date", as_index=False)
            .agg(
                outdoor_temp_c=("outdoor_temp_c", "mean"),
                elec_heating_kwh=("elec_heating_kwh", "sum"),
                gas_heating_kwh=("gas_heating_kwh", "sum"),
                total_heating_kwh=("total_heating_kwh", "sum"),
            )
            .dropna(subset=["outdoor_temp_c"])
            .sort_values("outdoor_temp_c")
        )

        fit = _fit_prism_model(daily, "outdoor_temp_c", "total_heating_kwh")

        ax.scatter(daily["outdoor_temp_c"], daily["elec_heating_kwh"], s=18, color="royalblue", alpha=0.45)
        ax.scatter(daily["outdoor_temp_c"], daily["gas_heating_kwh"], s=18, color="firebrick", alpha=0.45)
        ax.scatter(daily["outdoor_temp_c"], daily["total_heating_kwh"], s=18, color="darkgreen", alpha=0.45)

        if len(fit["temp"]) > 0 and np.isfinite(fit["r2"]):
            order = np.argsort(fit["temp"])
            prism_label = f"PRISM fit  Tbal={fit['t_balance']:.1f}°C  R²={fit['r2']:.2f}"
            ax.plot(fit["temp"][order], fit["pred"][order], color="black", linewidth=2, label=prism_label)
            ax.annotate(prism_label, xy=(0.02, 0.95), xycoords="axes fraction", fontsize=8, va="top")

        ax.set_title(f"Building {bid}")
        ax.set_ylabel("Daily Heating Energy (kWh)")

    for i in range(n):
        axes[i].set_xlabel("Outdoor Drybulb Temperature (°C)")

    for ax in axes[n:]:
        ax.set_visible(False)

    fig.legend(handles=legend_handles, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("PRISM-style HVAC Heating Signature (Energy vs Outdoor Temperature)", y=1.02, fontsize=13)
    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"PRISM heating signature plot saved to: {output_file}")


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
        json.dump({str(k): v for k, v in heating_vars.items()}, f, indent=2)
    print(f"\nHeating summary saved to: {output_file}")


def main(results_dir: str = "results", output_dir: str = str(DEFAULT_OUTPUT_DIR)):
    """
    Main function to analyze HVAC heating loads.

    Args:
        results_dir: Path to results directory
        output_dir: Directory where generated HVAC analysis artifacts are saved
    """
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Figures will be saved to: {output_dir}")
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
    
    # Extract hourly heating variables from timeseries
    heating_vars = extract_heating_variables(timeseries)

    # Print and save hourly summary
    print_heating_summary(heating_vars)
    save_heating_summary(heating_vars, output_file=os.path.join(output_dir, "hvac_heating_summary.json"))

    # Extract and print annual heating totals from metadata
    if not metadata.empty:
        annual_heating = extract_annual_heating_from_metadata(metadata)
        print("\n" + "="*80)
        print("ANNUAL HEATING TOTALS FROM METADATA")
        print("="*80)
        print(annual_heating.to_string(index=False))

    # Plot timeseries for each building
    plot_heating_timeseries(timeseries, output_file=os.path.join(output_dir, "hvac_heating_timeseries.png"))

    # Plot PRISM-style heating signature (energy vs outdoor drybulb)
    plot_prism_heating_signature(timeseries, output_file=os.path.join(output_dir, "hvac_heating_prism.png"))


if __name__ == "__main__":
    import sys

    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else str(DEFAULT_OUTPUT_DIR)
    main(results_dir, output_dir)
