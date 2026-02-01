# src/main.py
from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline.run_analysis import run


def _existing_file(p: str) -> str:
    path = Path(p)
    if not path.exists() or not path.is_file():
        raise argparse.ArgumentTypeError(f"File does not exist: {p}")
    return p


def _existing_dir(p: str) -> str:
    path = Path(p)
    if not path.exists() or not path.is_dir():
        raise argparse.ArgumentTypeError(f"Directory does not exist: {p}")
    return p


def _out_dir(p: str) -> str:
    """
    Output directory: create it if it doesn't exist.
    """
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="NASA battery preprocessing: metadata mapping -> RUL -> time-series features -> merged dataset."
    )

    ap.add_argument(
        "--metadata",
        required=True,
        type=_existing_file,
        help="Path to metadata file (CSV/XLSX).",
    )
    ap.add_argument(
        "--raw_root",
        required=True,
        type=_existing_dir,
        help="Root directory containing per-cycle time-series CSV files.",
    )
    ap.add_argument(
        "--out_dir",
        default="outputs/run_001",
        type=_out_dir,
        help="Output directory (will be created if missing).",
    )
    ap.add_argument(
        "--alpha",
        type=float,
        default=0.7,
        help="EOL threshold fraction for RUL (EOL = alpha * initial_capacity). Typical: 0.7–0.8",
    )
    ap.add_argument(
        "--non_interactive",
        action="store_true",
        help="Disable interactive prompts for column mapping.",
    )

    args = ap.parse_args()

    outputs = run(
        metadata_path=args.metadata,
        raw_root=args.raw_root,
        out_dir=args.out_dir,
        alpha=args.alpha,
        non_interactive=args.non_interactive,
    )

    print("\n✅ Done. Outputs:")
    for k, v in outputs.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
