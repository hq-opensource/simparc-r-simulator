#!/usr/bin/env python3
"""
Script to analyze HVAC heating loads from simulation results.

This script reads the simulation results metadata and timeseries data
and extracts heating variables for electricity and natural gas.
"""

import os
import pandas as pd
import json
import numpy as np
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots


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


def plot_heating_timeseries(timeseries: pd.DataFrame, output_file: str = "hvac_heating_timeseries.html"):
    """
    Plot electricity and natural gas heating timeseries for each building.

    Args:
        timeseries: DataFrame with timeseries data (all buildings)
        output_file: Output HTML file path
    """
    elec_col = next((c for c in timeseries.columns if c == "End Use: Electricity: Heating_kWh"), None)
    gas_col  = next((c for c in timeseries.columns if c == "End Use: Natural Gas: Heating_kBtu"), None)
    time_col = next((c for c in timeseries.columns if c == "Time"), None)

    if not elec_col and not gas_col:
        print("No heating columns found for plotting")
        return

    building_ids = sorted(timeseries["building_id"].unique())
    n = len(building_ids)

    fig = make_subplots(
        rows=n, cols=1,
        shared_xaxes=True,
        subplot_titles=[f"Building {bid}" for bid in building_ids],
        vertical_spacing=0.06,
    )

    for row_idx, bid in enumerate(building_ids, start=1):
        df = timeseries[timeseries["building_id"] == bid].sort_values(time_col or timeseries.columns[0])
        x = df[time_col] if time_col else df.index

        if elec_col:
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=df[elec_col].fillna(0),
                    name="Electricity Heating (kWh)",
                    line=dict(color="royalblue", width=1),
                    legendgroup="electricity",
                    showlegend=(row_idx == 1),
                ),
                row=row_idx, col=1,
            )

        if gas_col:
            kbtu_to_kwh = 0.293071
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=(df[gas_col].fillna(0) * kbtu_to_kwh),
                    name="Natural Gas Heating (kWh)",
                    line=dict(color="firebrick", width=1),
                    legendgroup="gas",
                    showlegend=(row_idx == 1),
                ),
                row=row_idx, col=1,
            )

        fig.update_yaxes(title_text="Energy (kWh)", row=row_idx, col=1)

    fig.update_layout(
        title="HVAC Heating Loads — Electricity vs Natural Gas",
        height=350 * n,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )

    fig.write_html(output_file)
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


def plot_prism_heating_signature(timeseries: pd.DataFrame, output_file: str = "hvac_heating_prism.html"):
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

    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        subplot_titles=[f"Building {bid}" for bid in building_ids],
        vertical_spacing=0.06,
    )

    for row_idx, bid in enumerate(building_ids, start=1):
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

        fig.add_trace(
            go.Scattergl(
                x=daily["outdoor_temp_c"],
                y=daily["elec_heating_kwh"],
                mode="markers",
                marker=dict(size=5, color="royalblue", opacity=0.45),
                name="Electricity Heating",
                legendgroup="elec",
                showlegend=(row_idx == 1),
            ),
            row=row_idx,
            col=1,
        )

        fig.add_trace(
            go.Scattergl(
                x=daily["outdoor_temp_c"],
                y=daily["gas_heating_kwh"],
                mode="markers",
                marker=dict(size=5, color="firebrick", opacity=0.45),
                name="Natural Gas Heating",
                legendgroup="gas",
                showlegend=(row_idx == 1),
            ),
            row=row_idx,
            col=1,
        )

        fig.add_trace(
            go.Scattergl(
                x=daily["outdoor_temp_c"],
                y=daily["total_heating_kwh"],
                mode="markers",
                marker=dict(size=5, color="darkgreen", opacity=0.45),
                name="Total Heating",
                legendgroup="total",
                showlegend=(row_idx == 1),
            ),
            row=row_idx,
            col=1,
        )

        if len(fit["temp"]) > 0 and np.isfinite(fit["r2"]):
            order = np.argsort(fit["temp"])
            label = f"Heat Load (PRISM fit, Tbal={fit['t_balance']:.1f}C, R2={fit['r2']:.2f})"
            fig.add_trace(
                go.Scatter(
                    x=fit["temp"][order],
                    y=fit["pred"][order],
                    mode="lines",
                    line=dict(color="black", width=2),
                    name=label,
                    legendgroup="prism",
                    showlegend=(row_idx == 1),
                ),
                row=row_idx,
                col=1,
            )

        fig.update_yaxes(title_text="Daily Heating Energy (kWh)", row=row_idx, col=1)

    fig.update_xaxes(title_text="Outdoor Drybulb Temperature (C)", row=n, col=1)
    fig.update_layout(
        title="PRISM-style HVAC Heating Signature (Energy vs Outdoor Temperature)",
        height=360 * n,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="closest",
    )
    fig.write_html(output_file)
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
    
    # Extract hourly heating variables from timeseries
    heating_vars = extract_heating_variables(timeseries)

    # Print and save hourly summary
    print_heating_summary(heating_vars)
    save_heating_summary(heating_vars)

    # Extract and print annual heating totals from metadata
    if not metadata.empty:
        annual_heating = extract_annual_heating_from_metadata(metadata)
        print("\n" + "="*80)
        print("ANNUAL HEATING TOTALS FROM METADATA")
        print("="*80)
        print(annual_heating.to_string(index=False))

    # Plot timeseries for each building
    plot_heating_timeseries(timeseries)

    # Plot PRISM-style heating signature (energy vs outdoor drybulb)
    plot_prism_heating_signature(timeseries)


if __name__ == "__main__":
    import sys
    
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    main(results_dir)
