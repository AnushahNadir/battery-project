# src/pipeline/run_analysis.py
from __future__ import annotations
from pathlib import Path
import json

from src.pipeline.data_loader import load_metadata, save_csv
from src.pipeline.mapper import build_rename_map
from src.analysis.rul import build_cycle_table_from_metadata, add_rul
from src.analysis.degradation_features import build_timeseries_features

def run(metadata_path: str | Path, raw_root: str | Path, out_dir: str | Path, alpha: float, non_interactive: bool):
    out_dir = Path(out_dir)
    raw_root = Path(raw_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Load metadata
    meta = load_metadata(metadata_path)

    # 2) Standardize metadata
    rename_map = build_rename_map(meta.columns, kind="meta", interactive=(not non_interactive))
    (out_dir / "mapping_used.json").write_text(json.dumps(rename_map, indent=2), encoding="utf-8")
    meta_std = meta.rename(columns=rename_map).copy()
    save_csv(meta_std, out_dir / "metadata_standardized.csv")

    # 3) RUL from metadata (discharge table)
    cycle_table = build_cycle_table_from_metadata(meta_std)
    cycle_rul = add_rul(cycle_table, alpha=alpha)
    save_csv(cycle_rul, out_dir / "cycle_table_with_rul.csv")

    # 4) Time-series features RIGHT NOW
    ts_feat = build_timeseries_features(cycle_rul[["battery_id","cycle_index","filename"]], raw_root=raw_root)
    save_csv(ts_feat, out_dir / "time_series_features.csv")

    merged = cycle_rul.merge(ts_feat, on=["battery_id","cycle_index","filename"], how="left")
    save_csv(merged, out_dir / "cycle_features_with_rul.csv")

    return {
        "metadata_standardized": str(out_dir / "metadata_standardized.csv"),
        "cycle_table_with_rul": str(out_dir / "cycle_table_with_rul.csv"),
        "time_series_features": str(out_dir / "time_series_features.csv"),
        "cycle_features_with_rul": str(out_dir / "cycle_features_with_rul.csv"),
        "mapping_used": str(out_dir / "mapping_used.json"),
    }
