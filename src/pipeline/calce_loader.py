# src/pipeline/calce_loader.py
"""
CALCE CS2 dataset loader.

Reads the raw Arbin XLS files for CS2_35 / CS2_36 / CS2_37 / CS2_38
and converts them to the same cycle-level format as the NASA pipeline output:

    battery_id | cycle_index | capacity | temp_mean | temp_max |
    v_mean | v_min | i_mean | i_min | energy_j | ah_est | duration_s

Each CS2 battery has 25-28 XLS files covering sequential test sessions.
The Cycle_Index resets to 1 in every file, so we renumber continuously.

Key extraction logic
---------------------
- Discharge step identified by negative Current(A).
- Per-cycle capacity = max Discharge_Capacity(Ah) within that cycle's
  discharge rows (Arbin accumulates it within each step, so the max
  is the total discharge capacity for that cycle).
- Temperature, voltage, current statistics computed over discharge rows.
- Energy = trapezoidal integration of Voltage × |Current| over time.
- Duration = total discharge time in seconds.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# CALCE CS2 nominal capacity (Ah)
CALCE_NOMINAL_CAPACITY = 1.1

# Minimum discharge capacity to count as a real discharge cycle
# (filters out impedance test pulses)
MIN_DISCHARGE_CAPACITY = 0.3  # Ah


def _read_arbin_sheet(path: str | Path) -> pd.DataFrame | None:
    """
    Read the Channel_* sheet from one Arbin XLS file.
    Returns a DataFrame with standard column names, or None if unreadable.
    """
    path = Path(path)
    try:
        xl = pd.ExcelFile(path)
    except Exception as exc:
        logger.warning(f"Cannot open {path.name}: {exc}")
        return None

    data_sheets = [s for s in xl.sheet_names if s.lower().startswith("channel")]
    if not data_sheets:
        logger.warning(f"No Channel sheet in {path.name}")
        return None

    try:
        raw = pd.read_excel(path, sheet_name=data_sheets[0], header=None)
    except Exception as exc:
        logger.warning(f"Cannot read sheet in {path.name}: {exc}")
        return None

    if raw.empty or len(raw) < 2:
        return None

    # Row 0 is the header
    raw.columns = raw.iloc[0]
    raw = raw.iloc[1:].reset_index(drop=True)

    # Normalise column names
    col_map = {}
    for c in raw.columns:
        cs = str(c).strip()
        if cs == "Cycle_Index":           col_map[c] = "cycle_index"
        elif cs == "Current(A)":          col_map[c] = "current_a"
        elif cs == "Voltage(V)":          col_map[c] = "voltage_v"
        elif cs == "Discharge_Capacity(Ah)": col_map[c] = "discharge_cap_ah"
        elif cs == "Charge_Capacity(Ah)": col_map[c] = "charge_cap_ah"
        elif cs == "Discharge_Energy(Wh)": col_map[c] = "discharge_energy_wh"
        elif cs == "Test_Time(s)":        col_map[c] = "test_time_s"
        elif cs == "Step_Time(s)":        col_map[c] = "step_time_s"
        elif cs == "Temp":                col_map[c] = "temperature_c"
        elif cs == "Internal_Resistance(Ohm)": col_map[c] = "resistance_ohm"

    raw = raw.rename(columns=col_map)

    required = {"cycle_index", "current_a", "voltage_v", "discharge_cap_ah"}
    missing = required - set(raw.columns)
    if missing:
        logger.warning(f"Missing columns {missing} in {path.name}")
        return None

    for col in ["cycle_index", "current_a", "voltage_v", "discharge_cap_ah",
                "test_time_s", "step_time_s", "temperature_c",
                "discharge_energy_wh", "resistance_ohm"]:
        if col in raw.columns:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")

    return raw


def _extract_cycles_from_file(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract one summary row per cycle from the raw Arbin time-series.
    Returns DataFrame with columns:
        local_cycle | capacity | temp_mean | temp_max | v_mean | v_min |
        i_mean | i_min | energy_j | ah_est | duration_s

    Important: Arbin accumulates Discharge_Capacity(Ah) across ALL cycles
    within a file (it never resets between cycles). So per-cycle capacity
    = max(discharge_cap in cycle N) - max(discharge_cap in cycle N-1).
    """
    rows = []

    # Pre-compute cumulative max discharge capacity per cycle
    cycle_ids = sorted(df["cycle_index"].dropna().unique())
    prev_cum_cap = 0.0  # cumulative discharge capacity before this cycle

    for cyc_id in cycle_ids:
        grp = df[df["cycle_index"] == cyc_id]

        # Discharge rows: negative current
        dis = grp[grp["current_a"] < -0.01].copy()
        if dis.empty:
            # No discharge in this cycle — update cumulative cap and skip
            cum_cap = float(grp["discharge_cap_ah"].max()) if grp["discharge_cap_ah"].notna().any() else prev_cum_cap
            if cum_cap > prev_cum_cap:
                prev_cum_cap = cum_cap
            continue

        # Cumulative discharge capacity at end of this cycle
        cum_cap_now = float(dis["discharge_cap_ah"].max())

        # Actual per-cycle capacity = delta from previous cumulative value
        cap = cum_cap_now - prev_cum_cap
        prev_cum_cap = cum_cap_now

        if cap < MIN_DISCHARGE_CAPACITY:
            continue

        # Temperature
        if "temperature_c" in dis.columns and dis["temperature_c"].notna().any():
            temp_vals = dis["temperature_c"].dropna().values
            temp_mean = float(np.mean(temp_vals))
            temp_max  = float(np.max(temp_vals))
        else:
            temp_mean = 25.0
            temp_max  = 25.0

        # Voltage stats
        v_vals = dis["voltage_v"].dropna().values
        v_mean = float(np.mean(v_vals)) if len(v_vals) else np.nan
        v_min  = float(np.min(v_vals))  if len(v_vals) else np.nan

        # Current stats (use absolute values for magnitude)
        i_vals = np.abs(dis["current_a"].dropna().values)
        i_mean = float(np.mean(i_vals)) if len(i_vals) else np.nan
        i_min  = float(np.min(i_vals))  if len(i_vals) else np.nan

        # Duration in seconds
        if "step_time_s" in dis.columns and dis["step_time_s"].notna().any():
            duration_s = float(dis["step_time_s"].max())
        elif "test_time_s" in dis.columns and dis["test_time_s"].notna().any():
            t = dis["test_time_s"].dropna().values
            duration_s = float(t[-1] - t[0]) if len(t) > 1 else 0.0
        else:
            duration_s = np.nan

        # Energy in Joules — trapz integration of V × |I| over time
        if ("test_time_s" in dis.columns
                and dis["test_time_s"].notna().sum() > 1
                and dis["voltage_v"].notna().sum() > 1):
            t_arr  = dis["test_time_s"].dropna().values
            v_arr  = dis["voltage_v"].dropna().values
            i_arr  = np.abs(dis["current_a"].dropna().values)
            min_len = min(len(t_arr), len(v_arr), len(i_arr))
            if min_len > 1:
                power  = v_arr[:min_len] * i_arr[:min_len]
                energy_j = float(np.trapz(power, t_arr[:min_len]))
            else:
                energy_j = cap * v_mean * 3600 if np.isfinite(v_mean) else np.nan
        elif "discharge_energy_wh" in dis.columns:
            ewh = dis["discharge_energy_wh"].max()
            energy_j = float(ewh * 3600) if pd.notna(ewh) else np.nan
        else:
            energy_j = cap * v_mean * 3600 if np.isfinite(v_mean) else np.nan

        # Ah estimate (same as capacity from Arbin)
        ah_est = cap

        rows.append({
            "local_cycle":  int(cyc_id),
            "capacity":     cap,
            "temp_mean":    temp_mean,
            "temp_max":     temp_max,
            "v_mean":       v_mean,
            "v_min":        v_min,
            "i_mean":       i_mean,
            "i_min":        i_min,
            "energy_j":     energy_j,
            "ah_est":       ah_est,
            "duration_s":   duration_s,
        })

    return pd.DataFrame(rows)


def load_calce_battery(battery_id: str, calce_root: str | Path) -> pd.DataFrame:
    """
    Load all XLS files for one CS2 battery and return a clean cycle table.

    Parameters
    ----------
    battery_id : str
        e.g. "CS2_35"
    calce_root : Path
        Root folder containing CS2_35/, CS2_36/, etc.

    Returns
    -------
    DataFrame with columns matching NASA cycle_features output:
        battery_id | cycle_index | capacity | temp_mean | temp_max |
        v_mean | v_min | i_mean | i_min | energy_j | ah_est | duration_s
    """
    calce_root = Path(calce_root)
    bat_dir    = calce_root / battery_id / battery_id

    if not bat_dir.exists():
        # Try one level up
        bat_dir = calce_root / battery_id
        if not bat_dir.exists():
            raise FileNotFoundError(f"Battery folder not found: {bat_dir}")

    files = sorted([f for f in os.listdir(bat_dir) if f.endswith(".xlsx")])
    if not files:
        raise FileNotFoundError(f"No .xlsx files found in {bat_dir}")

    logger.info(f"[CALCE] Loading {battery_id}: {len(files)} files from {bat_dir}")

    all_cycles: list[pd.DataFrame] = []
    global_cycle_offset = 0

    for fname in files:
        fpath = bat_dir / fname
        raw   = _read_arbin_sheet(fpath)
        if raw is None or raw.empty:
            continue

        cycles = _extract_cycles_from_file(raw)
        if cycles.empty:
            continue

        # Renumber cycles continuously across files
        cycles["cycle_index"] = cycles["local_cycle"] + global_cycle_offset
        global_cycle_offset   = int(cycles["cycle_index"].max())
        all_cycles.append(cycles.drop(columns=["local_cycle"]))

    if not all_cycles:
        raise ValueError(f"No valid cycles extracted for {battery_id}")

    combined = pd.concat(all_cycles, ignore_index=True)
    combined.insert(0, "battery_id", battery_id)
    combined = combined.sort_values("cycle_index").reset_index(drop=True)

    logger.info(
        f"[CALCE] {battery_id}: {len(combined)} cycles extracted, "
        f"capacity range {combined['capacity'].min():.3f}–{combined['capacity'].max():.3f} Ah"
    )
    return combined


def load_all_calce_batteries(
    calce_root: str | Path,
    battery_ids: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load all CS2 batteries and return a single combined DataFrame.
    """
    calce_root  = Path(calce_root)
    battery_ids = battery_ids or ["CS2_35", "CS2_36", "CS2_37", "CS2_38"]

    frames = []
    for bid in battery_ids:
        try:
            df = load_calce_battery(bid, calce_root)
            frames.append(df)
        except Exception as exc:
            logger.error(f"[CALCE] Failed to load {bid}: {exc}")

    if not frames:
        raise ValueError("No CALCE batteries loaded successfully.")

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        f"[CALCE] Total: {len(combined)} cycles across "
        f"{combined['battery_id'].nunique()} batteries"
    )
    return combined
