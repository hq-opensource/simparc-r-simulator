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

# Energy unit conversion: OpenStudio end-use columns report electricity in kWh
# and fossil/wood fuels in kBtu. Convert the latter to kWh for a common basis.
KBTU_TO_KWH = 0.293071

# Fallback simulation timestep when it cannot be inferred from the time column.
DEFAULT_TIMESTEP_HOURS = 0.25

# Consistent fuel-based colour palette used across all plots.
# Primary and backup scatter colours are drawn from this map so that
# "electricity" is always royalblue regardless of which system it belongs to.
FUEL_COLORS: dict[str, str] = {
    "electricity": "royalblue",
    "natural_gas": "firebrick",
    "wood": "darkorange",
    "fuel_oil": "maroon",
}
_DEFAULT_COLOR = "slategray"

# Fuel keys used consistently across per-fuel aggregations.
FUEL_KEYS = ("electricity", "natural_gas", "wood", "fuel_oil")



def _find_end_use_heating_columns(timeseries: pd.DataFrame) -> dict[str, list[str]]:
    """
    Return end-use heating columns grouped by fuel.

    We intentionally keep this strict to avoid accidentally grabbing unrelated
    columns (e.g., setpoints or non-end-use metrics).
    """
    cols = list(timeseries.columns)

    def match(prefix: str) -> list[str]:
        return [c for c in cols if c.startswith(prefix)]

    return {
        "electricity": match("End Use: Electricity: Heating"),
        "natural_gas": match("End Use: Natural Gas: Heating"),
        "wood": match("End Use: Wood") and [
            c for c in cols if c.startswith("End Use: Wood") and ": Heating" in c
        ] or [],
        "fuel_oil": match("End Use: Fuel Oil: Heating"),
    }


def _has_backup(value: object) -> bool:
    """True when a metadata field indicates a configured system/fuel."""
    s = str(value).strip().lower()
    return s not in {"", "nan", "none", "no", "false", "0"}


def _normalize_fuel_key(value: object) -> str | None:
    """Map a metadata fuel label to one of the FUEL_KEYS, or None."""
    s = str(value).strip().lower().replace("_", " ")
    if s in {"", "nan", "none"}:
        return None
    if "electric" in s:
        return "electricity"
    if "natural gas" in s or s == "gas":
        return "natural_gas"
    if "fuel oil" in s or "mazout" in s or s == "oil":
        return "fuel_oil"
    if "wood" in s or "pellet" in s:
        return "wood"
    return None


def _sum_cols(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Row-wise sum of the given columns, or a zero series when none exist."""
    return df[cols].fillna(0.0).sum(axis=1) if cols else pd.Series(0.0, index=df.index)


def _per_fuel_kwh_step(df: pd.DataFrame, heating_cols: dict[str, list[str]]) -> dict[str, pd.Series]:
    """Per-timestep heating energy (kWh) for each fuel, on a common kWh basis."""
    return {
        "electricity": _sum_cols(df, heating_cols["electricity"]),
        "natural_gas": _sum_cols(df, heating_cols["natural_gas"]) * KBTU_TO_KWH,
        "wood": _sum_cols(df, heating_cols["wood"]) * KBTU_TO_KWH,
        "fuel_oil": _sum_cols(df, heating_cols["fuel_oil"]) * KBTU_TO_KWH,
    }


def _select_backup_series(row: pd.Series, per_fuel: dict[str, pd.Series]) -> pd.Series:
    """
    Return the per-timestep backup heating series for a Heating System 2 building.

    Prefers the explicitly configured secondary fuel. When that fuel is not
    present (or shared with the primary), infers the backup as the largest
    non-primary fuel contribution. Returns a zero series when no backup fuel
    can be identified.
    """
    index = next(iter(per_fuel.values())).index
    hs2_fuel = _normalize_fuel_key(row.get("heating_system_2_fuel", None))
    if hs2_fuel in per_fuel:
        return per_fuel[hs2_fuel]

    if _has_backup(row.get("heating_system_2_type", None)):
        primary_fuel = _normalize_fuel_key(row.get("heating_system_fuel", None))
        candidates = {
            fk: s for fk, s in per_fuel.items()
            if fk != primary_fuel and float(s.sum()) > 0
        }
        if candidates:
            inferred = max(candidates, key=lambda k: float(candidates[k].sum()))
            return per_fuel[inferred]

    return pd.Series(0.0, index=index)


def _get_backup_fuel_key(row: pd.Series, per_fuel: dict[str, pd.Series]) -> str | None:
    """Return the fuel key for the backup system.

    Prefers the explicit heating_system_2_fuel column (present when the building
    CSV includes system-2 columns). Falls back to inferring from per-fuel energy
    consumption when that column is absent (older results without system-2 export).
    """
    hs2_fuel = _normalize_fuel_key(row.get("heating_system_2_fuel", None))
    if hs2_fuel is not None:
        return hs2_fuel
    if _has_backup(row.get("heating_system_2_type", None)):
        primary_fuel = _normalize_fuel_key(row.get("heating_system_fuel", None))
        candidates = {
            fk: s for fk, s in per_fuel.items()
            if fk != primary_fuel and float(s.sum()) > 0
        }
        if candidates:
            return max(candidates, key=lambda k: float(candidates[k].sum()))
    return None


def _prepare_metadata(metadata: pd.DataFrame) -> pd.DataFrame:
    """Normalize building_id to a clean integer column."""
    md = metadata.copy()
    md["building_id"] = pd.to_numeric(md["building_id"], errors="coerce")
    md = md.dropna(subset=["building_id"])
    md["building_id"] = md["building_id"].astype(int)
    return md


def _system2_building_ids(md: pd.DataFrame) -> list[int]:
    """Building ids that have a configured Heating System 2 (backup)."""
    if "heating_system_2_type" not in md.columns:
        return []
    mask = md["heating_system_2_type"].map(_has_backup)
    return sorted(md.loc[mask, "building_id"].unique())


def _get_system1_efficiency(row: pd.Series) -> float:
    """Get heating efficiency for System 1 (primary). Default 1.0 if missing."""
    eff = row.get("heating_system_heating_efficiency", 1.0)
    try:
        return float(eff) if eff not in {None, "", "nan", "none"} else 1.0
    except (ValueError, TypeError):
        return 1.0


def _get_system2_efficiency(row: pd.Series) -> float:
    """Get heating efficiency for System 2 (backup). Default 1.0 if missing."""
    eff = row.get("heating_system_2_heating_efficiency", 1.0)
    try:
        return float(eff) if eff not in {None, "", "nan", "none"} else 1.0
    except (ValueError, TypeError):
        return 1.0



def load_metadata(results_dir: str = "results") -> pd.DataFrame:
    """
    Load metadata from parquet dataset.

    If the parquet is missing system-2 columns (heating_system_2_fuel,
    heating_system_2_heating_efficiency) they are back-filled from the building
    stock CSV, using building_id as a 1-based row index into that file.

    Args:
        results_dir: Path to results directory

    Returns:
        DataFrame with metadata
    """
    metadata_path = os.path.join(results_dir, "metadata.parquet")
    if not os.path.exists(metadata_path):
        print(f"Metadata directory not found: {metadata_path}")
        return pd.DataFrame()

    metadata = pd.read_parquet(metadata_path)
    print(f"Loaded metadata: {metadata.shape[0]} rows, {metadata.shape[1]} columns")

    # Back-fill system columns that may not have been exported to the parquet.
    _SYS_COLS = [
        "heating_system_type",
        "heating_system_fuel",
        "heating_system_heating_efficiency",
        "heating_system_2_type",
        "heating_system_2_fuel",
        "heating_system_2_heating_efficiency",
    ]
    missing = [c for c in _SYS_COLS if c not in metadata.columns or metadata[c].isna().all()]
    if missing and "building_id" in metadata.columns:
        # Locate the building stock CSV: prefer the one named *hvac-system-2*.
        csv_candidates = sorted(Path(results_dir).parent.glob("test-building-stock-csv/building-hvac-system-2.csv"))
        if not csv_candidates:
            csv_candidates = sorted(Path(results_dir).parent.glob("test-building-stock-csv/*.csv"))
        for csv_path in csv_candidates:
            try:
                bdf = pd.read_csv(csv_path, usecols=lambda c: c in _SYS_COLS)
                if any(c in bdf.columns for c in missing):
                    # CSV rows are 0-indexed; parquet building_id starts at 1.
                    # So CSV row 0 → building_id 1, row 1 → building_id 2, etc.
                    bdf.index = bdf.index + 1
                    bdf.index.name = "building_id"
                    bdf = bdf.reset_index()
                    for col in missing:
                        if col in bdf.columns:
                            metadata = metadata.merge(
                                bdf[["building_id", col]],
                                on="building_id", how="left", suffixes=("", "_csv")
                            )
                            # Use CSV value where parquet had it missing.
                            if f"{col}_csv" in metadata.columns:
                                metadata[col] = metadata[col].combine_first(metadata.pop(f"{col}_csv"))
                    print(f"  Back-filled system-2 columns from {csv_path.name}")
                    break
            except Exception:
                continue

    return metadata


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


def _subplot_grid(n_plots: int, max_cols: int = 3) -> tuple[int, int]:
    """
    Compute a compact subplot grid for n_plots.
    """
    cols = min(max_cols, max(1, n_plots))
    rows = math.ceil(n_plots / cols)
    return rows, cols


def _infer_timestep_hours(df: pd.DataFrame, time_col: str | None) -> float:
    """
    Infer simulation timestep from the time column using modal time difference.
    Returns 0.25 h (15 min) when inference is not possible.
    """
    if not time_col or time_col not in df.columns:
        return 0.25

    t = pd.to_datetime(df[time_col], errors="coerce").dropna().sort_values()
    if len(t) < 2:
        return 0.25

    dt_hours = t.diff().dropna().dt.total_seconds() / 3600.0
    dt_hours = dt_hours[(dt_hours > 0) & np.isfinite(dt_hours)]
    if dt_hours.empty:
        return 0.25

    inferred = float(dt_hours.mode().iloc[0])
    return inferred if inferred > 0 else 0.25


def _outdoor_temp_c_series(df: pd.DataFrame) -> pd.Series | None:
    """
    Return outdoor drybulb in C if available.
    """
    if "Weather: Drybulb Temperature_C" in df.columns:
        return pd.to_numeric(df["Weather: Drybulb Temperature_C"], errors="coerce")
    if "Weather: Drybulb Temperature_F" in df.columns:
        temp_f = pd.to_numeric(df["Weather: Drybulb Temperature_F"], errors="coerce")
        return (temp_f - 32.0) * 5.0 / 9.0
    return None


def plot_capacity_switch_vs_temperature(
    timeseries: pd.DataFrame,
    metadata: pd.DataFrame,
    output_file: str = "hvac_primary_backup_capacity_vs_temp.png",
):
    """
    Plot primary/backup delivered capacity (kW) vs outdoor temperature.

    Each scatter point is one 15-min timestep.  Per-1°C bin statistics overlay:
    - Q95 line: near-rated capacity envelope (sizing signal).
    - Mean line: average delivered load at that temperature.
    Buildings with a heat-pump primary are excluded (temperature-dependent COP
    not captured by a scalar efficiency).
    """
    if metadata.empty:
        print("No metadata available; skipping capacity switch plot")
        return

    if "building_id" not in metadata.columns:
        print("No building_id in metadata; skipping capacity switch plot")
        return

    heating_cols = _find_end_use_heating_columns(timeseries)
    time_col = next((c for c in ["Time", "TimeUTC"] if c in timeseries.columns), None)

    if not any(heating_cols.values()):
        print("No heating end-use columns found; skipping capacity switch plot")
        return

    md = _prepare_metadata(metadata)
    backup_bids = _system2_building_ids(md)
    if "heating_system_2_type" not in md.columns:
        print("No heating_system_2_type in metadata; skipping capacity switch plot")
        return
    # Exclude heat-pump primaries: none of them have an active Heating System 2,
    # and their COP is temperature-dependent (not captured by a scalar efficiency).
    if "heat_pump_type" in md.columns:
        hp_bids = {int(b) for b in md.loc[md["heat_pump_type"].map(_has_backup), "building_id"]}
        backup_bids = [b for b in backup_bids if b not in hp_bids]
    if not backup_bids:
        print("No buildings with heating_system_2_type found; skipping capacity switch plot")
        return

    rows, cols = _subplot_grid(len(backup_bids), max_cols=2)
    fig, axes = plt.subplots(rows, cols, figsize=(7.0 * cols, 4.2 * rows), sharex=False, sharey=False)
    axes = np.array(axes).reshape(-1)

    tcap_by_bid: dict[int, float] = {}

    for i, bid in enumerate(backup_bids):
        ax = axes[i]
        bdf = timeseries[timeseries["building_id"] == bid].copy()
        if bdf.empty:
            ax.set_visible(False)
            continue

        if time_col:
            bdf[time_col] = pd.to_datetime(bdf[time_col], errors="coerce")
            bdf = bdf.dropna(subset=[time_col]).sort_values(time_col)

        dt_h = _infer_timestep_hours(bdf, time_col)
        temp_c = _outdoor_temp_c_series(bdf)
        if temp_c is None:
            ax.set_title(f"Building {bid} (no weather temp)")
            ax.set_visible(True)
            continue

        row = md.loc[md["building_id"] == bid]
        if row.empty:
            ax.set_title(f"Building {bid} (missing metadata)")
            continue
        row = row.iloc[0]

        per_fuel_kwh_step = _per_fuel_kwh_step(bdf, heating_cols)
        total_kwh_step = sum(per_fuel_kwh_step.values())
        backup_kwh_step = _select_backup_series(row, per_fuel_kwh_step)
        primary_kwh_step = (total_kwh_step - backup_kwh_step).clip(lower=0.0)

        # Convert fuel-side energy to delivered capacity using source efficiency.
        # Heat-pump primaries are already excluded above, so a scalar efficiency
        # (1.0 for electric resistance, furnace/boiler AFUE otherwise) is valid.
        sys1_eff = _get_system1_efficiency(row)
        sys2_eff = _get_system2_efficiency(row)
        primary_kw = pd.to_numeric(primary_kwh_step / dt_h * sys1_eff, errors="coerce").fillna(0.0)
        backup_kw = pd.to_numeric(backup_kwh_step / dt_h * sys2_eff, errors="coerce").fillna(0.0)

        work = pd.DataFrame({
            "temp_c": pd.to_numeric(temp_c, errors="coerce"),
            "primary_kw": primary_kw,
            "backup_kw": backup_kw,
        }).dropna(subset=["temp_c"])

        work = work[(work["primary_kw"] + work["backup_kw"]) > 1e-6]
        if work.empty:
            ax.set_title(f"Building {bid} (no heating steps)")
            continue

        ax.scatter(work["temp_c"], work["primary_kw"], s=6, alpha=0.25,
                   color=FUEL_COLORS.get(_normalize_fuel_key(row.get("heating_system_fuel")) or "", _DEFAULT_COLOR))
        ax.scatter(work["temp_c"], work["backup_kw"], s=6, alpha=0.22,
                   color=FUEL_COLORS.get(_get_backup_fuel_key(row, per_fuel_kwh_step) or "", _DEFAULT_COLOR))

        work["temp_bin"] = np.round(work["temp_c"]).astype(int)
        binned = (
            work.groupby("temp_bin", as_index=False)
            .agg(
                primary_q95=("primary_kw", lambda x: float(np.nanquantile(x, 0.95)) if len(x) else np.nan),
                primary_mean=("primary_kw", "mean"),
                backup_q95=("backup_kw", lambda x: float(np.nanquantile(x[x > 0.05], 0.95)) if (x > 0.05).sum() >= 5 else np.nan),
                backup_on_frac=("backup_kw", lambda x: float((x > 0.05).mean()) if len(x) else np.nan),
                n=("primary_kw", "size"),
            )
            .sort_values("temp_bin")
        )

        valid = binned[binned["n"] >= 20]
        cap_temp = np.nan
        if not valid.empty:
            cold_valid = valid[valid["temp_bin"] <= 5]
            ref = cold_valid["primary_q95"].max() if not cold_valid.empty else valid["primary_q95"].max()
            if np.isfinite(ref) and ref > 0:
                candidates = valid[
                    (valid["backup_on_frac"] >= 0.05)
                    & (valid["primary_q95"] >= 0.95 * ref)
                ]
                if not candidates.empty:
                    cap_temp = float(candidates["temp_bin"].max())

        if np.isfinite(cap_temp):
            tcap_by_bid[bid] = cap_temp

        ax.plot(valid["temp_bin"], valid["primary_q95"], color="black", linewidth=2.0, label="Primary Q95")

        if np.isfinite(cap_temp):
            ax.axvline(cap_temp, color="darkgreen", linestyle="--", linewidth=1.5)
            ax.annotate(f"Tcap~{cap_temp:.0f}C", xy=(cap_temp, ax.get_ylim()[1] * 0.92), fontsize=8, color="darkgreen")

        # System-type label box (top-right).
        sys1_type = str(row.get("heating_system_type", "")).strip() or str(row.get("heat_pump_type", "")).strip() or "?"
        sys1_fuel = str(row.get("heating_system_fuel", "")).strip()
        sys1_eff_val = _get_system1_efficiency(row)
        sys2_type = str(row.get("heating_system_2_type", "")).strip() or "?"
        sys2_fuel = _get_backup_fuel_key(row, per_fuel_kwh_step) or ""
        sys2_eff_val = _get_system2_efficiency(row)
        sys1_label = f"{sys1_type} ({sys1_fuel}, η={sys1_eff_val:.2f})" if sys1_fuel else f"{sys1_type} (η={sys1_eff_val:.2f})"
        sys2_label = f"{sys2_type} ({sys2_fuel}, η={sys2_eff_val:.2f})" if sys2_fuel else f"{sys2_type} (η={sys2_eff_val:.2f})"
        ax.text(
            0.97, 0.97,
            f"Primary: {sys1_label}\nBackup:   {sys2_label}",
            transform=ax.transAxes, fontsize=7, va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray", alpha=0.85),
        )

        # Backup plateau box (top-left) — coloured by backup fuel.
        backup_color = FUEL_COLORS.get(sys2_fuel, _DEFAULT_COLOR)
        cold_both = valid[(valid["temp_bin"] <= cap_temp if np.isfinite(cap_temp) else True) & valid["backup_q95"].notna()]
        if not cold_both.empty:
            primary_plateau = float(cold_both["primary_q95"].median())
            backup_plateau = float(cold_both["backup_q95"].median())
            total_plateau = primary_plateau + backup_plateau
            if total_plateau > 0:
                backup_frac = backup_plateau / total_plateau
                ax.text(
                    0.03, 0.97,
                    f"Backup plateau: {backup_frac*100:.0f}%\n({backup_plateau:.1f} / {total_plateau:.1f} kW)",
                    transform=ax.transAxes, fontsize=8, va="top", ha="left",
                    color=backup_color,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=backup_color, alpha=0.75),
                )

        ax.set_title(f"Building {bid}")
        ax.set_xlabel("Outdoor Temperature (°C)")
        ax.set_ylabel("Delivered Capacity (kW)")

    for ax in axes[len(backup_bids):]:
        ax.set_visible(False)

    handles = [
        mlines.Line2D([], [], color="royalblue", marker="o", linestyle="None", markersize=4, alpha=0.5, label="Electricity (15-min)"),
        mlines.Line2D([], [], color="firebrick", marker="o", linestyle="None", markersize=4, alpha=0.5, label="Natural gas (15-min)"),
        mlines.Line2D([], [], color="darkorange", marker="o", linestyle="None", markersize=4, alpha=0.5, label="Wood (15-min)"),
        mlines.Line2D([], [], color="maroon", marker="o", linestyle="None", markersize=4, alpha=0.5, label="Fuel oil (15-min)"),
        mlines.Line2D([], [], color="black", linewidth=2, label="Primary Q95 per °C bin"),
        mlines.Line2D([], [], color="darkgreen", linestyle="--", linewidth=1.5, label="Estimated cap temp"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=6, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Primary/Backup Delivered Capacity vs Outdoor Temperature (Buildings with Heating System 2)", y=1.02, fontsize=13)
    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Capacity switch plot saved to: {output_file}")
    return tcap_by_bid


def report_primary_backup_split(
    timeseries: pd.DataFrame,
    metadata: pd.DataFrame,
):
    """
    Report the actual primary/backup heating load split for buildings with Heating System 2.

    For each System 2 building, computes total energy supplied by primary and backup
    systems (as fractions and kWh) across the entire simulation.
    """
    if metadata.empty or timeseries.empty:
        print("Missing metadata or timeseries; skipping primary/backup split report")
        return

    heating_cols = _find_end_use_heating_columns(timeseries)
    md = _prepare_metadata(metadata)
    if "heating_system_2_type" not in md.columns:
        print("No heating_system_2_type in metadata; skipping primary/backup split report")
        return

    backup_bids = _system2_building_ids(md)
    if not backup_bids:
        print("No buildings with heating_system_2_type found; skipping primary/backup split report")
        return

    print("\n" + "=" * 80)
    print("PRIMARY/BACKUP HEATING LOAD SPLIT (Heating System 2 Buildings)")
    print("=" * 80)

    results = []
    for bid in backup_bids:
        bdf = timeseries[timeseries["building_id"] == bid]
        if bdf.empty:
            continue

        row = md.loc[md["building_id"] == bid]
        if row.empty:
            continue
        row = row.iloc[0]

        per_fuel_kwh_step = _per_fuel_kwh_step(bdf, heating_cols)
        total_kwh = float(sum(s.sum() for s in per_fuel_kwh_step.values()))
        if total_kwh <= 0:
            continue

        backup_kwh = float(_select_backup_series(row, per_fuel_kwh_step).sum())
        primary_kwh = max(0.0, total_kwh - backup_kwh)
        primary_frac = primary_kwh / total_kwh
        backup_frac = backup_kwh / total_kwh

        # Compute delivered heat (energy × efficiency)
        sys1_eff = _get_system1_efficiency(row)
        sys2_eff = _get_system2_efficiency(row)
        primary_delivered_kwh = primary_kwh * sys1_eff
        backup_delivered_kwh = backup_kwh * sys2_eff
        total_delivered_kwh = primary_delivered_kwh + backup_delivered_kwh
        
        if total_delivered_kwh > 0:
            primary_delivered_frac = primary_delivered_kwh / total_delivered_kwh
            backup_delivered_frac = backup_delivered_kwh / total_delivered_kwh
        else:
            primary_delivered_frac = 0.0
            backup_delivered_frac = 0.0

        results.append((bid, primary_kwh, backup_kwh, primary_frac, backup_frac, total_kwh,
                        primary_delivered_kwh, backup_delivered_kwh, primary_delivered_frac, backup_delivered_frac, total_delivered_kwh))

    if not results:
        print("No valid System 2 buildings found")
        return

    results.sort(key=lambda x: x[3], reverse=True)  # sort by primary fraction descending

    print(f"\n{'Building':<10}{'Primary %':<12}{'Backup %':<12}{'Primary kWh':<16}{'Backup kWh':<16}{'Total kWh':<16}")
    print("-" * 90)
    for bid, prim_kwh, backup_kwh, prim_frac, backup_frac, total_kwh, *delivered in results:
        print(
            f"{bid:<10}{prim_frac*100:>10.1f}%  {backup_frac*100:>10.1f}%  "
            f"{prim_kwh:>14.0f}   {backup_kwh:>14.0f}   {total_kwh:>14.0f}"
        )

    avg_primary = np.mean([x[3] for x in results])
    avg_backup = np.mean([x[4] for x in results])
    print("-" * 90)
    print(f"{'Average':<10}{avg_primary*100:>10.1f}%  {avg_backup*100:>10.1f}%")

    # Print delivered heat split
    print(f"\n--- DELIVERED HEAT SPLIT (accounting for system efficiency) ---")
    print(f"{'Building':<10}{'Primary %':<12}{'Backup %':<12}{'Primary kWh':<16}{'Backup kWh':<16}{'Total kWh':<16}")
    print("-" * 90)
    for bid, prim_kwh, backup_kwh, prim_frac, backup_frac, total_kwh, prim_deliv, backup_deliv, prim_deliv_frac, backup_deliv_frac, total_deliv in results:
        print(
            f"{bid:<10}{prim_deliv_frac*100:>10.1f}%  {backup_deliv_frac*100:>10.1f}%  "
            f"{prim_deliv:>14.0f}   {backup_deliv:>14.0f}   {total_deliv:>14.0f}"
        )

    avg_primary_deliv = np.mean([x[8] for x in results])
    avg_backup_deliv = np.mean([x[9] for x in results])
    print("-" * 90)
    print(f"{'Average':<10}{avg_primary_deliv*100:>10.1f}%  {avg_backup_deliv*100:>10.1f}%")


def report_primary_backup_capacity_extreme_cold(
    timeseries: pd.DataFrame,
    metadata: pd.DataFrame,
    temp_min: float = -30.0,
    temp_max: float = -15.0,
):
    """
    Report primary/backup CAPACITY (kW, not energy) during extreme cold conditions.

    Filters to timesteps with outdoor temperature in [temp_min, temp_max] range
    and computes average instantaneous capacity usage during extreme cold.
    """
    if metadata.empty or timeseries.empty:
        print("Missing metadata or timeseries; skipping extreme cold capacity report")
        return

    # Find temperature column
    temp_col = next((c for c in ["Weather: Drybulb Temperature_C", "Weather: Drybulb Temperature_F"] if c in timeseries.columns), None)
    if temp_col is None:
        print("No outdoor drybulb temperature column found; skipping extreme cold capacity report")
        return

    dt_h = DEFAULT_TIMESTEP_HOURS
    heating_cols = _find_end_use_heating_columns(timeseries)

    # Convert temperature to Celsius if needed
    if temp_col.endswith("_F"):
        temp_c = (timeseries[temp_col].astype(float) - 32.0) * 5.0 / 9.0
    else:
        temp_c = timeseries[temp_col].astype(float)

    md = _prepare_metadata(metadata)
    if "heating_system_2_type" not in md.columns:
        print("No heating_system_2_type in metadata; skipping extreme cold capacity report")
        return

    backup_bids = _system2_building_ids(md)
    if not backup_bids:
        print("No buildings with heating_system_2_type found; skipping extreme cold capacity report")
        return

    print("\n" + "=" * 80)
    print(f"PRIMARY/BACKUP CAPACITY DURING EXTREME COLD ({temp_min}°C to {temp_max}°C)")
    print("=" * 80)

    # Prepare working dataframe with temperature column
    working = timeseries.copy()
    working["outdoor_temp_c"] = temp_c

    results = []
    for bid in backup_bids:
        bdf = working[working["building_id"] == bid]
        if bdf.empty:
            continue

        # Filter to extreme cold timesteps
        extreme_cold_mask = (bdf["outdoor_temp_c"] >= temp_min) & (bdf["outdoor_temp_c"] <= temp_max)
        bdf_extreme = bdf[extreme_cold_mask]
        if bdf_extreme.empty:
            continue

        row = md.loc[md["building_id"] == bid]
        if row.empty:
            continue
        row = row.iloc[0]

        # Mean instantaneous capacity (kW) per fuel over the extreme-cold window.
        per_fuel_kwh_step = _per_fuel_kwh_step(bdf_extreme, heating_cols)
        per_fuel_kw_mean = {fk: float((s / dt_h).mean()) for fk, s in per_fuel_kwh_step.items()}

        total_kw_mean = sum(per_fuel_kw_mean.values())
        if total_kw_mean <= 0:
            continue

        backup_kw_mean = float((_select_backup_series(row, per_fuel_kwh_step) / dt_h).mean())
        primary_kw_mean = max(0.0, total_kw_mean - backup_kw_mean)
        primary_frac = primary_kw_mean / total_kw_mean
        backup_frac = backup_kw_mean / total_kw_mean

        # Delivered capacity (power × efficiency)
        sys1_eff = _get_system1_efficiency(row)
        sys2_eff = _get_system2_efficiency(row)
        primary_delivered_kw = primary_kw_mean * sys1_eff
        backup_delivered_kw = backup_kw_mean * sys2_eff
        total_delivered_kw = primary_delivered_kw + backup_delivered_kw
        
        if total_delivered_kw > 0:
            primary_delivered_frac = primary_delivered_kw / total_delivered_kw
            backup_delivered_frac = backup_delivered_kw / total_delivered_kw
        else:
            primary_delivered_frac = 0.0
            backup_delivered_frac = 0.0

        timesteps_in_range = len(bdf_extreme)
        results.append((bid, primary_kw_mean, backup_kw_mean, primary_frac, backup_frac, total_kw_mean, timesteps_in_range,
                        primary_delivered_kw, backup_delivered_kw, primary_delivered_frac, backup_delivered_frac, total_delivered_kw))

    if not results:
        print(f"No buildings with extreme cold data ({temp_min}°C to {temp_max}°C)")
        return

    results.sort(key=lambda x: x[4], reverse=True)  # sort by backup capacity fraction descending

    print(f"\n{'Building':<10}{'Primary %':<12}{'Backup %':<12}{'Primary kW':<14}{'Backup kW':<14}{'Total kW':<14}{'Timesteps':<12}")
    print("-" * 100)
    for bid, prim_kw, backup_kw, prim_frac, backup_frac, total_kw, n_steps, *delivered in results:
        print(
            f"{bid:<10}{prim_frac*100:>10.1f}%  {backup_frac*100:>10.1f}%  "
            f"{prim_kw:>12.2f}   {backup_kw:>12.2f}   {total_kw:>12.2f}   {n_steps:>10d}"
        )

    avg_primary_cap = np.mean([x[3] for x in results])
    avg_backup_cap = np.mean([x[4] for x in results])
    print("-" * 100)
    print(f"{'Average':<10}{avg_primary_cap*100:>10.1f}%  {avg_backup_cap*100:>10.1f}%")

    # Print delivered capacity split
    print(f"\n--- DELIVERED CAPACITY (accounting for system efficiency) ---")
    print(f"{'Building':<10}{'Primary %':<12}{'Backup %':<12}{'Primary kW':<14}{'Backup kW':<14}{'Total kW':<14}{'Timesteps':<12}")
    print("-" * 100)
    for bid, prim_kw, backup_kw, prim_frac, backup_frac, total_kw, n_steps, prim_deliv, backup_deliv, prim_deliv_frac, backup_deliv_frac, total_deliv in results:
        print(
            f"{bid:<10}{prim_deliv_frac*100:>10.1f}%  {backup_deliv_frac*100:>10.1f}%  "
            f"{prim_deliv:>12.2f}   {backup_deliv:>12.2f}   {total_deliv:>12.2f}   {n_steps:>10d}"
        )

    avg_primary_deliv = np.mean([x[9] for x in results])
    avg_backup_deliv = np.mean([x[10] for x in results])
    print("-" * 100)
    print(f"{'Average':<10}{avg_primary_deliv*100:>10.1f}%  {avg_backup_deliv*100:>10.1f}%")


def plot_heating_timeseries(timeseries: pd.DataFrame, output_file: str = "hvac_heating_timeseries.png"):
    """
    Plot daily electricity, natural gas, wood, and fuel oil heating energy for each building.

    Args:
        timeseries: DataFrame with timeseries data (all buildings)
        output_file: Output PNG file path
    """
    heating_cols = _find_end_use_heating_columns(timeseries)
    elec_cols = heating_cols["electricity"]
    gas_cols = heating_cols["natural_gas"]
    wood_cols = heating_cols["wood"]
    oil_cols = heating_cols["fuel_oil"]
    time_col = next((c for c in timeseries.columns if c == "Time"), None)

    if not elec_cols and not gas_cols and not wood_cols and not oil_cols:
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
    if elec_cols:
        legend_handles.append(mlines.Line2D([], [], color="royalblue", linewidth=1, label="Electricity Heating (kWh)"))
    if gas_cols:
        legend_handles.append(mlines.Line2D([], [], color="firebrick", linewidth=1, label="Natural Gas Heating (kWh)"))
    if wood_cols:
        legend_handles.append(mlines.Line2D([], [], color="darkorange", linewidth=1, label="Wood Heating (kWh)"))
    if oil_cols:
        legend_handles.append(mlines.Line2D([], [], color="maroon", linewidth=1, label="Fuel Oil Heating (kWh)"))

    for i, bid in enumerate(building_ids):
        ax = axes[i]
        df = timeseries[timeseries["building_id"] == bid].copy()

        if time_col and time_col in df.columns:
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.dropna(subset=[time_col]).sort_values(time_col)
            df["date"] = df[time_col].dt.floor("D")
            x = None
        else:
            df = df.sort_index()
            x = df.index

        elec = df[elec_cols].fillna(0.0).sum(axis=1) if elec_cols else pd.Series(0.0, index=df.index)
        gas = df[gas_cols].fillna(0.0).sum(axis=1) * KBTU_TO_KWH if gas_cols else pd.Series(0.0, index=df.index)
        wood = df[wood_cols].fillna(0.0).sum(axis=1) * KBTU_TO_KWH if wood_cols else pd.Series(0.0, index=df.index)
        oil = df[oil_cols].fillna(0.0).sum(axis=1) * KBTU_TO_KWH if oil_cols else pd.Series(0.0, index=df.index)

        if "date" in df.columns:
            daily = pd.DataFrame({
                "date": df["date"],
                "elec": elec,
                "gas": gas,
                "wood": wood,
                "oil": oil,
            }).groupby("date", as_index=False).sum()
            x = daily["date"]

            if elec_cols:
                ax.plot(x, daily["elec"], color="royalblue", linewidth=0.8)
            if gas_cols:
                ax.plot(x, daily["gas"], color="firebrick", linewidth=0.8)
            if wood_cols:
                ax.plot(x, daily["wood"], color="darkorange", linewidth=0.8)
            if oil_cols:
                ax.plot(x, daily["oil"], color="maroon", linewidth=0.8)
        else:
            if elec_cols:
                ax.plot(x, elec, color="royalblue", linewidth=0.8)
            if gas_cols:
                ax.plot(x, gas, color="firebrick", linewidth=0.8)
            if wood_cols:
                ax.plot(x, wood, color="darkorange", linewidth=0.8)
            if oil_cols:
                ax.plot(x, oil, color="maroon", linewidth=0.8)

        ax.set_title(f"Building {bid}")
        ax.set_ylabel("Daily Energy (kWh/day)")
        ax.tick_params(axis="x", rotation=30)

    for ax in axes[n:]:
        ax.set_visible(False)

    if legend_handles:
        fig.legend(handles=legend_handles, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.0))

    fig.suptitle("HVAC Daily Heating Energy — Electricity, Natural Gas, Wood, and Fuel Oil", y=1.02, fontsize=13)
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
    - Wood heating (converted to kWh if needed)
    - Fuel oil heating (converted to kWh if needed)
    - Total heating energy
    - PRISM fitted heat-load curve
    """
    temp_col = next((c for c in ["Weather: Drybulb Temperature_C", "Weather: Drybulb Temperature_F"] if c in timeseries.columns), None)
    if temp_col is None:
        print("No outdoor drybulb temperature column found; skipping PRISM plot")
        return

    heating_cols = _find_end_use_heating_columns(timeseries)
    elec_cols = heating_cols["electricity"]
    gas_cols = heating_cols["natural_gas"]
    wood_cols = heating_cols["wood"]
    oil_cols = heating_cols["fuel_oil"]
    time_col = next((c for c in timeseries.columns if c in ["Time", "TimeUTC"]), None)

    if time_col is None:
        print("No time column found; skipping PRISM plot")
        return

    if not elec_cols and not gas_cols and not wood_cols and not oil_cols:
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
    working["elec_heating_kwh"] = working[elec_cols].fillna(0.0).sum(axis=1) if elec_cols else 0.0
    gas_kwh = working[gas_cols].fillna(0.0).sum(axis=1) * KBTU_TO_KWH if gas_cols else 0.0
    working["gas_heating_kwh"] = gas_kwh
    wood_kwh = working[wood_cols].fillna(0.0).sum(axis=1) * KBTU_TO_KWH if wood_cols else 0.0
    working["wood_heating_kwh"] = wood_kwh
    oil_kwh = working[oil_cols].fillna(0.0).sum(axis=1) * KBTU_TO_KWH if oil_cols else 0.0
    working["oil_heating_kwh"] = oil_kwh
    working["total_heating_kwh"] = working["elec_heating_kwh"] + working["gas_heating_kwh"] + working["wood_heating_kwh"] + working["oil_heating_kwh"]
    working["date"] = working[time_col].dt.date

    building_ids = sorted(working["building_id"].unique())
    n = len(building_ids)

    if n == 0:
        print("No buildings found in timeseries; skipping PRISM plot")
        return

    rows, cols = _subplot_grid(n)
    fig, axes = plt.subplots(rows, cols, figsize=(6.2 * cols, 4.8 * rows))
    axes = np.array(axes).reshape(-1)

    tbase_by_bid: dict[int, float] = {}

    legend_handles = [
        mlines.Line2D([], [], color="royalblue", marker="o", markersize=4, linestyle="None", alpha=0.6, label="Electricity Heating"),
        mlines.Line2D([], [], color="firebrick", marker="o", markersize=4, linestyle="None", alpha=0.6, label="Natural Gas Heating"),
        mlines.Line2D([], [], color="darkorange", marker="o", markersize=4, linestyle="None", alpha=0.6, label="Wood Heating"),
        mlines.Line2D([], [], color="maroon", marker="o", markersize=4, linestyle="None", alpha=0.6, label="Fuel Oil Heating"),
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
                wood_heating_kwh=("wood_heating_kwh", "sum"),
                oil_heating_kwh=("oil_heating_kwh", "sum"),
                total_heating_kwh=("total_heating_kwh", "sum"),
            )
            .dropna(subset=["outdoor_temp_c"])
            .sort_values("outdoor_temp_c")
        )

        fit = _fit_prism_model(daily, "outdoor_temp_c", "total_heating_kwh")
        if np.isfinite(fit["t_balance"]):
            tbase_by_bid[int(bid)] = fit["t_balance"]

        ax.scatter(daily["outdoor_temp_c"], daily["elec_heating_kwh"], s=18, color="royalblue", alpha=0.45)
        ax.scatter(daily["outdoor_temp_c"], daily["gas_heating_kwh"], s=18, color="firebrick", alpha=0.45)
        ax.scatter(daily["outdoor_temp_c"], daily["wood_heating_kwh"], s=18, color="darkorange", alpha=0.45)
        ax.scatter(daily["outdoor_temp_c"], daily["oil_heating_kwh"], s=18, color="maroon", alpha=0.45)
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

    fig.legend(handles=legend_handles, loc="upper center", ncol=6, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("PRISM-style HVAC Heating Signature (Energy vs Outdoor Temperature)", y=1.02, fontsize=13)
    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"PRISM heating signature plot saved to: {output_file}")
    return tbase_by_bid


def plot_tbase_vs_tcap(
    tbase_by_bid: dict[int, float],
    tcap_by_bid: dict[int, float],
    output_file: str = "hvac_tbase_vs_tcap.png",
):
    """
    Scatter plot of PRISM balance temperature (T_base) vs capacity cap temperature
    (T_cap) for buildings that have both estimates.
    """
    common = sorted(set(tbase_by_bid) & set(tcap_by_bid))
    # Filter to buildings where T_base is in [0, 20]
    common = [b for b in common if 0.0 <= tbase_by_bid[b] <= 20.0]
    if not common:
        print("No buildings have both T_base (0–20 °C) and T_cap; skipping T_base vs T_cap scatter")
        return

    x = [tcap_by_bid[b] for b in common]
    y = [tbase_by_bid[b] for b in common]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(x, y, s=60, color="steelblue", zorder=3)

    for bid, tx, ty in zip(common, x, y):
        ax.annotate(
            str(bid),
            xy=(tx, ty),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
            color="black",
        )

    lim_min = min(min(x), min(y)) - 2
    lim_max = max(max(x), max(y)) + 2
    ax.plot([lim_min, lim_max], [lim_min, lim_max], "k--", linewidth=0.8, alpha=0.4, label="T_cap = T_base")

    ax.set_xlabel("T_cap — Estimated Primary Cap Temperature (°C)")
    ax.set_ylabel("T_base — PRISM Balance Temperature (°C)")
    ax.set_title("T_cap (Capacity Switch) vs T_base (PRISM)\nBuildings with Heating System 2 — T_base filtered to [0, 20] °C")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"T_base vs T_cap scatter saved to: {output_file}")


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
    
    # Report primary/backup heating load split for System 2 buildings
    report_primary_backup_split(timeseries, metadata)

    # Report primary/backup CAPACITY during extreme cold
    report_primary_backup_capacity_extreme_cold(timeseries, metadata, temp_min=-30.0, temp_max=-15.0)

    # Plot timeseries for each building (daily aggregation)
    plot_heating_timeseries(timeseries, output_file=os.path.join(output_dir, "hvac_heating_timeseries.png"))

    # Plot PRISM-style heating signature (energy vs outdoor drybulb)
    tbase_by_bid = plot_prism_heating_signature(
        timeseries, output_file=os.path.join(output_dir, "hvac_heating_prism.png")
    ) or {}

    # Plot primary/backup timestep capacity proxy vs outdoor temperature
    tcap_by_bid = plot_capacity_switch_vs_temperature(
        timeseries,
        metadata,
        output_file=os.path.join(output_dir, "hvac_primary_backup_capacity_vs_temp.png"),
    ) or {}

    # Scatter: PRISM T_base vs capacity cap T_cap
    plot_tbase_vs_tcap(
        tbase_by_bid,
        tcap_by_bid,
        output_file=os.path.join(output_dir, "hvac_tbase_vs_tcap.png"),
    )


if __name__ == "__main__":
    import sys

    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else str(DEFAULT_OUTPUT_DIR)
    main(results_dir, output_dir)
