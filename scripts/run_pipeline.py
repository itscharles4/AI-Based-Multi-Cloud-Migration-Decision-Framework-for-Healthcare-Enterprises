"""
run_pipeline.py
===============
One-shot pipeline runner for the telemedicine project.

Runs all three data preparation steps in sequence:
  1. data_generator.py  — generates synthetic IoMT telemetry CSV
  2. preprocessing.py   — scales data and builds sliding-window .npy files
  3. train.py           — trains the LSTM model and saves graphs

Usage
-----
  cd telemedicine-cloud-project
  python scripts/run_pipeline.py

  # Or with custom row count:
  python scripts/run_pipeline.py --rows 10000

  # Skip training (just generate + preprocess):
  python scripts/run_pipeline.py --no-train
"""

import argparse
import subprocess
import sys
import os
import time


def run_step(description, command, cwd="."):
    """Run a subprocess step, printing its output live."""
    bar = "=" * 65
    print(f"\n{bar}")
    print(f"  {description}")
    print(bar)
    start = time.time()
    result = subprocess.run(
        [sys.executable] + command,
        cwd=cwd,
    )
    elapsed = time.time() - start
    if result.returncode != 0:
        print(f"\n[FAIL] Step failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    print(f"\n[OK] Done in {elapsed:.1f}s")
    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Run the complete telemedicine ML pipeline end-to-end."
    )
    parser.add_argument(
        "--rows", type=int, default=20000,
        help="Number of rows to generate (default: 20000)"
    )
    parser.add_argument(
        "--no-train", action="store_true",
        help="Skip model training (only generate data + preprocess)"
    )
    args = parser.parse_args()

    # Resolve project root relative to this script
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))

    print("\n" + "=" * 65)
    print("  Telemedicine Pipeline — Full Run")
    print("=" * 65)
    print(f"  Project root : {project_root}")
    print(f"  Rows to gen  : {args.rows}")
    print(f"  Train model  : {'NO' if args.no_train else 'YES'}")

    total_time = 0.0

    # ── Step 1: Generate data ────────────────────────────────────────────────
    total_time += run_step(
        "Step 1/3 — Generating synthetic IoMT telemetry data",
        ["src/prediction/data_generator.py", "--rows", str(args.rows)],
        cwd=project_root,
    )

    # ── Step 2: Preprocess ───────────────────────────────────────────────────
    total_time += run_step(
        "Step 2/3 — Preprocessing: scaling + sliding windows",
        ["src/prediction/preprocessing.py"],
        cwd=project_root,
    )

    # ── Step 3: Train (optional) ─────────────────────────────────────────────
    if not args.no_train:
        total_time += run_step(
            "Step 3/3 — Training LSTM model (up to 50 epochs w/ EarlyStopping)",
            ["src/prediction/train.py"],
            cwd=project_root,
        )
    else:
        print("\n[SKIP] Step 3/3 — Training skipped (--no-train flag set)")

    print("\n" + "=" * 65)
    print(f"  Pipeline complete! Total time: {total_time:.1f}s")
    print("=" * 65)
    print("\nNext steps:")
    print("  pytest tests/ -v                         # run all tests")
    print("  uvicorn src.api.main:app --reload        # start API server")
    print("  python src/api/simulate_stream.py        # run live simulation")
    print("  streamlit run dashboard/app.py           # open dashboard")


if __name__ == "__main__":
    main()
