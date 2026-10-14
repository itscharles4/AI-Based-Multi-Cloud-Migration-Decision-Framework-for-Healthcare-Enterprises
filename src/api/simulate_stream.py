"""
simulate_stream.py
==================
End-to-end simulation runner for the telemedicine pipeline.

Loads data/raw/telemetry_data.csv, iterates through it in device-grouped
sliding windows of 20 readings, and POSTs each window to the FastAPI
/ingest endpoint.

Run this script while the API server is running:
  # Terminal 1:
  uvicorn src.api.main:app --reload

  # Terminal 2:
  python src/api/simulate_stream.py

This is the LIVE DEMO script — run it during the project review/viva.
"""

import os
import sys
import time
import math
import random
import json
import pandas as pd
import requests
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

API_URL      = "http://localhost:8000/ingest"
WINDOW_SIZE  = 20
SLEEP_DELAY  = 0.5    # seconds between requests (simulates live stream)
MAX_WINDOWS  = None   # set to an integer to limit total windows (None = process all)


def get_patient_criticality() -> float:
    """
    Randomly assign a patient criticality score.
    ~95% of events are routine (0-3), ~5% are emergencies (8-10).
    """
    if random.random() < 0.05:
        return round(random.uniform(8.0, 10.0), 1)
    return round(random.uniform(0.0, 3.0), 1)


def get_cloud_cost_index(timestamp: str) -> float:
    """
    Simulate a time-of-day-based cloud cost index using a sine wave.
    Peak cost at midday, lower cost at night — realistic for cloud spot pricing.
    """
    try:
        dt   = datetime.fromisoformat(timestamp.replace("Z", ""))
        hour = dt.hour + dt.minute / 60.0
        # Sine wave: peaks at 12:00 (noon), troughs at 00:00 (midnight)
        cost = 0.5 + 0.4 * math.sin(math.pi * (hour - 6) / 12)
        return round(max(0.0, min(1.0, cost)), 3)
    except Exception:
        return round(random.uniform(0.0, 1.0), 3)


def main():
    print("=" * 65)
    print("  Telemedicine Workload Offloader — Live Stream Simulation")
    print("=" * 65)
    print(f"  API endpoint : {API_URL}")
    print(f"  Window size  : {WINDOW_SIZE}")
    print(f"  Delay        : {SLEEP_DELAY}s per request")
    print("=" * 65)

    # Load telemetry data
    csv_path = os.path.join("data", "raw", "telemetry_data.csv")
    if not os.path.exists(csv_path):
        print(f"\n[simulate] ERROR: {csv_path} not found.")
        print("  Run: python src/prediction/data_generator.py  first.")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["device_id", "timestamp"]).reset_index(drop=True)

    devices      = df["device_id"].unique()
    total_events = 0
    errors       = 0

    print(f"\n[simulate] Loaded {len(df)} rows across {len(devices)} devices.\n")

    for device_id in devices:
        device_df = df[df["device_id"] == device_id].reset_index(drop=True)
        n_rows    = len(device_df)

        # Slide through the device's rows in non-overlapping windows
        for start in range(0, n_rows - WINDOW_SIZE, WINDOW_SIZE):
            if MAX_WINDOWS and total_events >= MAX_WINDOWS:
                break

            window_df = device_df.iloc[start: start + WINDOW_SIZE]

            # Convert to list of dicts (matching TelemetryRecord schema)
            window_list = []
            for _, row in window_df.iterrows():
                window_list.append({
                    "timestamp":           row["timestamp"].isoformat() + "Z",
                    "device_id":           row["device_id"],
                    "bandwidth_mbps":      float(row["bandwidth_mbps"]),
                    "packet_loss_pct":     float(row["packet_loss_pct"]),
                    "jitter_ms":           float(row["jitter_ms"]),
                    "signal_strength_dbm": float(row["signal_strength_dbm"]),
                    "current_latency_ms":  float(row["current_latency_ms"]),
                })

            criticality = get_patient_criticality()
            cost_index  = get_cloud_cost_index(window_list[-1]["timestamp"])

            payload = {
                "window":                     window_list,
                "patient_criticality_score":  criticality,
                "current_cloud_cost_index":   cost_index,
            }

            # POST to API
            try:
                resp = requests.post(API_URL, json=payload, timeout=10)
                resp.raise_for_status()
                result = resp.json()
                total_events += 1

                # One-line summary per request
                decision  = result.get("routing_decision", "?")
                latency   = result.get("predicted_latency_ms", 0)
                risk      = result.get("network_degradation_risk", "?")
                alerted   = "🚨" if result.get("alerted") else "  "
                reason    = result.get("reason", "?")[:25]

                print(
                    f"[{total_events:>4}] {device_id:<15}"
                    f"  crit={criticality:>4.1f}"
                    f"  lat={latency:>7.1f}ms"
                    f"  risk={risk:<6}"
                    f"  → {decision:<6}"
                    f"  {alerted} {reason}"
                )

            except requests.exceptions.ConnectionError:
                print(f"\n[simulate] ERROR: Cannot connect to {API_URL}.")
                print("  Make sure the API server is running:")
                print("  uvicorn src.api.main:app --reload\n")
                sys.exit(1)
            except Exception as e:
                errors += 1
                print(f"[simulate] Error on event {total_events}: {e}")

            time.sleep(SLEEP_DELAY)

        if MAX_WINDOWS and total_events >= MAX_WINDOWS:
            break

    print("\n" + "=" * 65)
    print(f"  Simulation complete. Events processed: {total_events}")
    print(f"  Errors: {errors}")
    print("=" * 65)


if __name__ == "__main__":
    main()
