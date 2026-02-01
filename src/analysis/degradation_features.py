# src/analysis/degradation_features.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd

from src.pipeline.mapper import standardize_columns


# Canonical TS names (MUST match schema.py keys)
TIME = "time"
V_MEAS = "voltage_measured"
I_MEAS = "current_measured"
T_MEAS = "temperature_measured"
I_LOAD = "current_load"
V_LOAD = "voltage_load"

REQUIRED_TS = [TIME, V_MEAS, I_MEAS, T_MEAS, I_LOAD, V_LOAD]


def _safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    """
    Version-safe trapezoidal integration.
    Works across old and new NumPy versions.
    """
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    else:
        # Old NumPy fallback
        return float(np.trapz(y, x))



def _resolve_ts_path(raw_root: Path, battery_id: str, filename: str) -> Optional[Path]:
    """
    Robust TS file resolver:
      1) raw_root/<filename>
      2) raw_root/<battery_id>/<filename>
      3) raw_root/**/<filename>   (recursive fallback)
    """
    p1 = raw_root / filename
    if p1.exists():
        return p1

    p2 = raw_root / battery_id / filename
    if p2.exists():
        return p2

    # recursive fallback (handles nested layouts like raw_root/data/05174.csv)
    matches = list(raw_root.rglob(filename))
    if matches:
        return matches[0]

    return None


def featurize_cycle_file(csv_path: Path) -> Dict[str, Any]:
    """
    Reads a single cycle CSV, standardizes columns to canonical schema names,
    then computes deterministic time-series features.

    IMPORTANT: All feature extraction uses canonical names:
      time, voltage_measured, current_measured, temperature_measured, current_load, voltage_load
    """
    df_raw = pd.read_csv(csv_path)

    # Stage-1 mapping: synonyms + value-hints (interactive off)
    df = standardize_columns(df_raw, kind="ts", interactive=False)

    # Coerce to numeric for canonical columns if present
    for c in REQUIRED_TS:
        if c in df.columns:
            df[c] = _safe_numeric(df[c])

    feat: Dict[str, Any] = {}

    # duration (seconds)
    if TIME in df.columns:
        t = df[TIME].dropna().to_numpy()
        feat["duration_s"] = float(np.max(t) - np.min(t)) if t.size else np.nan
    else:
        feat["duration_s"] = np.nan

    # temperature stats
    if T_MEAS in df.columns:
        temp = df[T_MEAS].dropna().to_numpy()
        feat["temp_mean"] = float(np.mean(temp)) if temp.size else np.nan
        feat["temp_max"] = float(np.max(temp)) if temp.size else np.nan
    else:
        feat["temp_mean"] = np.nan
        feat["temp_max"] = np.nan

    # voltage preference: use voltage_load if available else voltage_measured
    vcol = V_LOAD if V_LOAD in df.columns else (V_MEAS if V_MEAS in df.columns else None)
    if vcol is not None:
        v = df[vcol].dropna().to_numpy()
        feat["v_min"] = float(np.min(v)) if v.size else np.nan
        feat["v_mean"] = float(np.mean(v)) if v.size else np.nan
        feat["v_end"] = float(v[-1]) if v.size else np.nan
        feat["v_col_used"] = vcol
    else:
        feat["v_min"] = feat["v_mean"] = feat["v_end"] = np.nan
        feat["v_col_used"] = ""

    # current preference: use current_load if available else current_measured
    icol = I_LOAD if I_LOAD in df.columns else (I_MEAS if I_MEAS in df.columns else None)
    if icol is not None:
        i = df[icol].dropna().to_numpy()
        feat["i_mean"] = float(np.mean(i)) if i.size else np.nan
        feat["i_min"] = float(np.min(i)) if i.size else np.nan
        feat["i_col_used"] = icol
    else:
        feat["i_mean"] = feat["i_min"] = np.nan
        feat["i_col_used"] = ""

    # energy / Ah estimates (time-integrals)
    # Only compute if we have time + chosen vcol + chosen icol
    if TIME in df.columns and vcol is not None and icol is not None:
        t = df[TIME].to_numpy()
        v = df[vcol].to_numpy()
        i = df[icol].to_numpy()

        mask = np.isfinite(t) & np.isfinite(v) & np.isfinite(i)
        t, v, i = t[mask], v[mask], i[mask]

        if t.size >= 2:
            order = np.argsort(t)
            t, v, i = t[order], v[order], i[order]

            p = v * i
            feat["energy_j"] = _trapz(p, t)
            feat["ah_est"] = _trapz(i, t) / 3600.0
        else:
            feat["energy_j"] = np.nan
            feat["ah_est"] = np.nan
    else:
        feat["energy_j"] = np.nan
        feat["ah_est"] = np.nan

    return feat


def build_timeseries_features(cycle_table: pd.DataFrame, raw_root: Path) -> pd.DataFrame:
    """
    cycle_table must have: battery_id, cycle_index, filename

    Finds each TS file robustly (including nested folder layouts),
    standardizes columns, then computes deterministic per-cycle features.

    Output includes:
      - ts_found (bool)
      - ts_path (str) for debugging
      - extracted features (duration/temp/voltage/current/energy/Ah)
    """
    rows = []

    for _, r in cycle_table.iterrows():
        bid = str(r["battery_id"])
        fname = str(r["filename"])

        csv_path = _resolve_ts_path(raw_root, battery_id=bid, filename=fname)

        if csv_path is None:
            rows.append({
                "battery_id": bid,
                "cycle_index": int(r["cycle_index"]),
                "filename": fname,
                "ts_found": False,
                "ts_path": "",
            })
            continue

        feats = featurize_cycle_file(csv_path)
        feats.update({
            "battery_id": bid,
            "cycle_index": int(r["cycle_index"]),
            "filename": fname,
            "ts_found": True,
            "ts_path": str(csv_path),
        })
        rows.append(feats)

    return pd.DataFrame(rows)
