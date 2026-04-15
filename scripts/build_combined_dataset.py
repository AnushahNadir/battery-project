"""
Build combined NASA + CALCE dataset.

Steps:
1. Load NASA cycle_features_with_rul.csv (already preprocessed)
2. Load CALCE CS2_35/36/37/38 via calce_loader
3. Add RUL labels to CALCE batteries using the same add_rul() logic
4. Harmonise columns and merge
5. Write to data/processed/cycle_features_with_rul.csv (overwrite)
   and keep a backup of the original NASA-only version

Run from project root:
    python scripts/build_combined_dataset.py
"""
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline.calce_loader import load_all_calce_batteries
from src.analysis.rul import add_rul
from src.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = get_config()

    nasa_path   = ROOT / cfg.paths.processed_data / "cycle_features_with_rul.csv"
    calce_root  = ROOT / "data" / "calce"
    backup_path = ROOT / cfg.paths.processed_data / "cycle_features_with_rul_nasa_only.csv"
    out_path    = nasa_path  # overwrite in place

    # ── 1. Load NASA data ─────────────────────────────────────────────────────
    logger.info("Loading NASA dataset...")
    nasa_df = pd.read_csv(nasa_path)
    logger.info(f"  NASA: {len(nasa_df)} rows, {nasa_df['battery_id'].nunique()} batteries")

    # Backup original
    if not backup_path.exists():
        shutil.copy(nasa_path, backup_path)
        logger.info(f"  Backed up NASA-only dataset to {backup_path.name}")

    # ── 2. Load CALCE data ────────────────────────────────────────────────────
    logger.info("Loading CALCE CS2 dataset...")
    calce_raw = load_all_calce_batteries(
        calce_root,
        battery_ids=["CS2_35", "CS2_36", "CS2_37", "CS2_38"],
    )
    logger.info(f"  CALCE: {len(calce_raw)} rows, {calce_raw['battery_id'].nunique()} batteries")

    # ── 3. Add RUL labels to CALCE ────────────────────────────────────────────
    logger.info("Computing RUL for CALCE batteries (alpha=0.70)...")
    calce_with_rul = add_rul(calce_raw, alpha=0.70)

    # Log per-battery RUL info
    for bid, g in calce_with_rul.groupby("battery_id"):
        logger.info(
            f"  {bid}: init_cap={g['init_capacity'].iloc[0]:.3f}  "
            f"eol_thr={g['eol_capacity_threshold'].iloc[0]:.3f}  "
            f"eol_cycle={g['eol_cycle'].iloc[0]}  "
            f"first_RUL={g['RUL'].iloc[0]}  "
            f"cycles={len(g)}"
        )

    # ── 4. Harmonise columns ──────────────────────────────────────────────────
    logger.info("Harmonising columns...")

    # Columns present in NASA output
    nasa_cols = set(nasa_df.columns)

    # Add columns CALCE doesn't have (set to NaN — they weren't measured)
    for col in nasa_cols:
        if col not in calce_with_rul.columns:
            calce_with_rul[col] = np.nan

    # Keep only columns that exist in NASA (ensures schema match)
    calce_aligned = calce_with_rul.reindex(columns=nasa_df.columns)

    # Add v_end if present in NASA but missing from CALCE
    if "v_end" in nasa_df.columns and "v_end" not in calce_aligned.columns:
        calce_aligned["v_end"] = np.nan

    # ── 5. Merge ──────────────────────────────────────────────────────────────
    logger.info("Merging datasets...")
    combined = pd.concat([nasa_df, calce_aligned], ignore_index=True)
    combined = combined.sort_values(["battery_id", "cycle_index"]).reset_index(drop=True)

    logger.info(f"  Combined: {len(combined)} rows, {combined['battery_id'].nunique()} batteries")
    logger.info(f"  Batteries: {sorted(combined['battery_id'].astype(str).unique())}")

    # Sanity checks
    assert combined["battery_id"].notna().all(), "battery_id has nulls"
    assert combined["cycle_index"].notna().all(), "cycle_index has nulls"
    assert combined["RUL"].notna().all(), "RUL has nulls"
    rul_neg = (combined["RUL"] < 0).sum()
    if rul_neg:
        logger.warning(f"  {rul_neg} negative RUL values found — clipping to 0")
        combined["RUL"] = combined["RUL"].clip(lower=0)

    # ── 6. Write output ───────────────────────────────────────────────────────
    combined.to_csv(out_path, index=False)
    logger.info(f"  Written to {out_path}")
    logger.info("Done.")


if __name__ == "__main__":
    main()
