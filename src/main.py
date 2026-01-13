# src/main.py
from __future__ import annotations
import argparse
from src.pipeline.run_analysis import run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--raw_root", required=True)
    ap.add_argument("--out_dir", default="data/processed")
    ap.add_argument("--alpha", type=float, default=0.7)
    ap.add_argument("--non_interactive", action="store_true")
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
