import argparse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="battery-degradation-coscientist",
        description="Research pipeline for battery degradation analysis (NASA/CALCE-style).",
    )
    p.add_argument("--version", action="store_true", help="Print version and exit.")
    p.add_argument("--run-id", default="dev_run", help="Run identifier for records/experiments.")
    p.add_argument("--data-dir", default="data/raw", help="Path to raw data directory.")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print("battery-degradation-coscientist v0.1.0")
        return

    print("✅ Repo is set up and runnable.")
    print(f"Run ID: {args.run_id}")
    print(f"Data dir: {args.data_dir}")
    print("Next: implement src/pipeline/run_analysis.py and data loaders.")


if __name__ == "__main__":
    main()
