# src/pipeline/mapper.py
from __future__ import annotations
import re
from typing import Dict
import pandas as pd
from src.pipeline.schema import SYNONYMS_META, SYNONYMS_TS

def _normalize_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower())

def build_rename_map(df_cols, kind: str = "meta", interactive: bool = True) -> Dict[str, str]:
    """
    Maps raw columns -> canonical columns based on synonyms.
    kind: "meta" or "ts"
    """
    synonyms = SYNONYMS_META if kind == "meta" else SYNONYMS_TS

    raw_cols = list(df_cols)
    raw_norm = {_normalize_name(c): c for c in raw_cols}

    rename = {}
    used_raw = set()

    for canon, candidates in synonyms.items():
        found = None
        for cand in candidates:
            cand_norm = _normalize_name(cand)
            if cand_norm in raw_norm:
                found = raw_norm[cand_norm]
                break
        if found:
            rename[found] = canon
            used_raw.add(found)

    unknown = [c for c in raw_cols if c not in used_raw]
    if unknown and interactive:
        print(f"\n[Mapper] Unmapped columns detected ({kind}):")
        for c in unknown:
            print(f" - {c}")
        print("\nMap them to a canonical name, or press ENTER to skip.")
        for c in unknown:
            ans = input(f"Map '{c}' -> ").strip()
            if ans:
                rename[c] = ans

    return rename

def standardize_columns(df: pd.DataFrame, kind: str = "meta", interactive: bool = True) -> pd.DataFrame:
    rename = build_rename_map(df.columns, kind=kind, interactive=interactive)
    return df.rename(columns=rename).copy()
