# src/analysis/degradation_features.py
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

def _safe_numeric(s):
    return pd.to_numeric(s, errors="coerce")

def featurize_cycle_file(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)

    cols = ["Voltage_measured","Current_measured","Temperature_measured","Current_load","Voltage_load","Time"]
    for c in cols:
        if c in df.columns:
            df[c] = _safe_numeric(df[c])

    feat = {}

    # duration
    if "Time" in df.columns:
        t = df["Time"].dropna().values
        feat["duration_s"] = float(t.max() - t.min()) if len(t) else np.nan
    else:
        feat["duration_s"] = np.nan

    # temp
    if "Temperature_measured" in df.columns:
        temp = df["Temperature_measured"].dropna()
        feat["temp_mean"] = float(temp.mean()) if len(temp) else np.nan
        feat["temp_max"] = float(temp.max()) if len(temp) else np.nan
    else:
        feat["temp_mean"] = np.nan
        feat["temp_max"] = np.nan

    # voltage
    vcol = "Voltage_load" if "Voltage_load" in df.columns else ("Voltage_measured" if "Voltage_measured" in df.columns else None)
    if vcol:
        v = df[vcol].dropna()
        feat["v_min"] = float(v.min()) if len(v) else np.nan
        feat["v_mean"] = float(v.mean()) if len(v) else np.nan
        feat["v_end"] = float(v.iloc[-1]) if len(v) else np.nan
    else:
        feat["v_min"] = feat["v_mean"] = feat["v_end"] = np.nan

    # current
    icol = "Current_load" if "Current_load" in df.columns else ("Current_measured" if "Current_measured" in df.columns else None)
    if icol:
        i = df[icol].dropna()
        feat["i_mean"] = float(i.mean()) if len(i) else np.nan
        feat["i_min"] = float(i.min()) if len(i) else np.nan
    else:
        feat["i_mean"] = feat["i_min"] = np.nan

    # energy/Ah estimates
    if "Time" in df.columns and vcol and icol:
        t = df["Time"].values
        v = df[vcol].values
        i = df[icol].values
        mask = np.isfinite(t) & np.isfinite(v) & np.isfinite(i)
        t, v, i = t[mask], v[mask], i[mask]

        if len(t) >= 2:
            order = np.argsort(t)
            t, v, i = t[order], v[order], i[order]

            p = v * i
            if hasattr(np, "trapezoid"):
                trapz = np.trapezoid
            else:
                trapz = np.trapz
            feat["energy_j"] = float(trapz(p, t))
            feat["ah_est"] = float(trapz(i, t) / 3600.0)
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
    raw_root layout:
      - raw_root/<filename>
      - raw_root/<battery_id>/<filename>
    """
    rows = []
    for _, r in cycle_table.iterrows():
        bid = str(r["battery_id"])
        fname = str(r["filename"])

        p1 = raw_root / fname
        p2 = raw_root / bid / fname
        csv_path = p1 if p1.exists() else (p2 if p2.exists() else None)

        if csv_path is None:
            rows.append({
                "battery_id": bid,
                "cycle_index": int(r["cycle_index"]),
                "filename": fname,
                "ts_found": False
            })
            continue

        feats = featurize_cycle_file(csv_path)
        feats.update({
            "battery_id": bid,
            "cycle_index": int(r["cycle_index"]),
            "filename": fname,
            "ts_found": True
        })
        rows.append(feats)

    return pd.DataFrame(rows)
