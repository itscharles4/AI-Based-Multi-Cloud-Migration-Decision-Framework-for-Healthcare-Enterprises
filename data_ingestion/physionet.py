"""Download open PhysioNet vital-sign recordings (de-identified, public) to drive the
criticality input realistically. Default dataset: BIDMC (ICU recordings).

Usage:
    python data_ingestion/physionet.py --db bidmc --out data/raw/vitals
    python data_ingestion/physionet.py --db bidmc --max-records 20

IMPORTANT: The file/signal names inside a PhysioNet database differ by dataset.
This script prints what it finds. If the heart-rate / SpO2 / respiration channels
are not matched automatically, inspect `sig_name` in the output and adapt SIGNAL_MAP.

Falls back gracefully — the platform runs fine on simulated vitals if this fails.
Registration: https://physionet.org/register/ (free, instant approval for open datasets)
"""
import argparse
from pathlib import Path

import pandas as pd

# Signal name aliases for each vital sign target
SIGNAL_MAP = {
    "heart_rate": ("hr", "pulse", "heart_rate"),
    "spo2":       ("spo2", "sao2", "o2sat"),
    "resp_rate":  ("resp", "rr", "resp_rate", "respiratory"),
}


def match(names: list[str], keys: tuple[str, ...]) -> int | None:
    """Return the index of the first signal name matching any alias key."""
    for i, n in enumerate(names):
        if any(k in n.lower() for k in keys):
            return i
    return None


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Download PhysioNet ICU vitals for the telemedicine criticality model"
    )
    ap.add_argument("--db", default="bidmc",
                    help="PhysioNet database name (default: bidmc)")
    ap.add_argument("--out", default="data/raw/vitals",
                    help="Output directory for CSV files")
    ap.add_argument("--max-records", type=int, default=20,
                    help="Max number of records to download (default: 20)")
    a = ap.parse_args()

    try:
        import wfdb  # noqa: PLC0415
    except ImportError:
        print("ERROR: wfdb not installed. Run: pip install wfdb")
        raise SystemExit(1)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Downloading PhysioNet database: {a.db}")
    print(f"Output directory: {out.resolve()}")
    print(f"Max records: {a.max_records}\n")

    wfdb.dl_database(a.db, str(out / a.db))

    # Numeric (1 Hz) records usually end with 'n' in BIDMC; adapt if yours differ
    all_recs = wfdb.get_record_list(a.db)
    recs = [r for r in all_recs if r.endswith("n")][: a.max_records]

    if not recs:
        # Fallback: take first N records regardless of suffix
        recs = all_recs[: a.max_records]

    print(f"Found {len(recs)} numeric records: {recs}\n")

    saved = 0
    for rec in recs:
        try:
            record = wfdb.rdrecord(str(out / a.db / rec))
            print(f"Record {rec} — signals: {record.sig_name}")
            cols = {}
            for target, keys in SIGNAL_MAP.items():
                idx = match(record.sig_name, keys)
                if idx is not None:
                    cols[target] = record.p_signal[:, idx]
            if cols:
                out_path = out / f"{rec}.csv"
                pd.DataFrame(cols).to_csv(out_path, index_label="t_seconds")
                print(f"  ✅ Wrote {out_path} with columns: {list(cols)}")
                saved += 1
            else:
                print(f"  ⚠️  No matching signals found — skipping {rec}")
                print(f"       Available: {record.sig_name}")
                print(f"       Adapt SIGNAL_MAP if needed.")
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ Failed to process {rec}: {e}")

    print(f"\nDone. Saved {saved}/{len(recs)} records to {out.resolve()}")
    print("Next step: run scripts/run_pipeline.py to integrate vitals into model training.")


if __name__ == "__main__":
    main()
