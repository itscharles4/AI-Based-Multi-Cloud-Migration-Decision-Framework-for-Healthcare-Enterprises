"""
data_ingestion/ripe_atlas.py
=============================
Download real network latency measurements from RIPE Atlas.

RIPE Atlas is a global network measurement platform with 10,000+
probes worldwide. We use it to get real RTT (round-trip time)
measurements from hospital-like locations to cloud endpoints.

Setup:
  1. Register at https://atlas.ripe.net/accounts/register/
  2. Get your API key at https://atlas.ripe.net/keys/
  3. Set RIPE_API_KEY in your .env file

Usage:
  python data_ingestion/ripe_atlas.py --output data/raw/ripe_latency.csv
  python data_ingestion/ripe_atlas.py --msm-id 1001 --output data/raw/msm_1001.csv

What it downloads:
  - Built-in ping measurement results (measurement IDs like 1001, 1002, etc.)
  - Extracts: avg RTT, min RTT, packet loss, probe location
  - Formats to match our telemetry schema for LSTM training
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ATLAS_BASE = "https://atlas.ripe.net/api/v2"

# Built-in RIPE Atlas measurement IDs for common RTT measurements
# These are public measurements anyone can read (no API key needed for read)
BUILTIN_MEASUREMENTS = {
    "ping_google_dns":     1001,   # Ping to 8.8.8.8
    "ping_cloudflare":     1002,   # Ping to 1.1.1.1
    "ping_aws_eu_west":    1003,   # Ping to AWS eu-west-1
    "ping_azure_eu":       1004,   # Ping to Azure EU
}


def fetch_measurement_results(msm_id: int, api_key: str, hours: int = 24) -> list[dict]:
    """
    Download results for a RIPE Atlas measurement.
    Returns list of result dicts.
    """
    stop  = int(time.time())
    start = stop - (hours * 3600)

    params = {
        "start":    start,
        "stop":     stop,
        "format":   "json",
    }
    headers = {}
    if api_key:
        headers["Authorization"] = f"Key {api_key}"

    url = f"{ATLAS_BASE}/measurements/{msm_id}/results/"
    logger.info("Fetching measurement %d from RIPE Atlas...", msm_id)

    results = []
    next_url = url

    try:
        with httpx.Client(timeout=30.0, headers=headers) as client:
            while next_url:
                resp = client.get(next_url, params=params if next_url == url else None)
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    results.extend(data)
                    break
                elif isinstance(data, dict):
                    results.extend(data.get("results", []))
                    next_url = data.get("next")
                    params   = None   # next URL already has params
                else:
                    break

        logger.info("Downloaded %d results for measurement %d", len(results), msm_id)
    except httpx.HTTPStatusError as exc:
        logger.error("HTTP error: %s", exc)
    except Exception as exc:
        logger.error("Failed to fetch measurement: %s", exc)

    return results


def parse_ping_result(result: dict) -> dict | None:
    """
    Parse a single RIPE Atlas ping result into our telemetry schema.
    Returns None if the result is incomplete or failed.
    """
    try:
        avg_rtt = result.get("avg")
        min_rtt = result.get("min")
        max_rtt = result.get("max")
        sent    = result.get("sent", 0)
        rcvd    = result.get("rcvd", 0)

        if avg_rtt is None or avg_rtt <= 0:
            return None

        packet_loss = ((sent - rcvd) / max(sent, 1)) * 100
        jitter      = (max_rtt - min_rtt) if max_rtt and min_rtt else 0.0
        ts          = result.get("timestamp", int(time.time()))
        ts_str      = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        probe_id    = result.get("prb_id", 0)
        device_id   = f"RIPE-PROBE-{probe_id}"

        # Estimate bandwidth: RTT-based heuristic (lower RTT → higher bandwidth capacity)
        # Real data would come from traceroute measurements
        estimated_bandwidth = max(5.0, min(100.0, 200.0 / max(avg_rtt, 1)))
        estimated_signal    = max(-90.0, min(-40.0, -50.0 - (avg_rtt / 10.0)))

        return {
            "timestamp":           ts_str,
            "device_id":           device_id,
            "bandwidth_mbps":      round(estimated_bandwidth, 2),
            "packet_loss_pct":     round(packet_loss, 2),
            "jitter_ms":           round(jitter, 2),
            "signal_strength_dbm": round(estimated_signal, 1),
            "current_latency_ms":  round(avg_rtt, 2),
        }
    except Exception:
        return None


def download_to_csv(msm_id: int, output_path: str, api_key: str = "", hours: int = 24):
    """Download a RIPE Atlas measurement and save to CSV."""
    results = fetch_measurement_results(msm_id, api_key=api_key, hours=hours)
    if not results:
        logger.warning("No results downloaded for measurement %d", msm_id)
        return 0

    parsed  = [parse_ping_result(r) for r in results]
    valid   = [p for p in parsed if p is not None]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = ["timestamp", "device_id", "bandwidth_mbps", "packet_loss_pct",
                  "jitter_ms", "signal_strength_dbm", "current_latency_ms"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid)

    logger.info("Saved %d/%d valid readings to %s", len(valid), len(results), output_path)
    return len(valid)


def main():
    parser = argparse.ArgumentParser(description="Download RIPE Atlas latency data")
    parser.add_argument("--msm-id", type=int, default=1001,
                        help="RIPE Atlas measurement ID (default: 1001 = ping to 8.8.8.8)")
    parser.add_argument("--output", default="data/raw/ripe_latency.csv",
                        help="Output CSV path")
    parser.add_argument("--hours", type=int, default=24,
                        help="Hours of data to download (default: 24)")
    parser.add_argument("--api-key", default=settings.RIPE_API_KEY,
                        help="RIPE Atlas API key (or set RIPE_API_KEY in .env)")
    parser.add_argument("--all-builtin", action="store_true",
                        help="Download all built-in measurements and merge")
    args = parser.parse_args()

    if args.all_builtin:
        all_rows = []
        for name, msm_id in BUILTIN_MEASUREMENTS.items():
            results = fetch_measurement_results(msm_id, api_key=args.api_key, hours=args.hours)
            parsed  = [parse_ping_result(r) for r in results if r]
            valid   = [p for p in parsed if p is not None]
            # Tag device_id with measurement name
            for row in valid:
                row["device_id"] = f"{name.upper()}-{row['device_id'].split('-')[-1]}"
            all_rows.extend(valid)

        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        fieldnames = ["timestamp", "device_id", "bandwidth_mbps", "packet_loss_pct",
                      "jitter_ms", "signal_strength_dbm", "current_latency_ms"]
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        logger.info("Combined %d total readings → %s", len(all_rows), args.output)
    else:
        download_to_csv(args.msm_id, args.output, api_key=args.api_key, hours=args.hours)

    print(f"\nNext step: use this CSV to retrain the LSTM:")
    print(f"  python scripts/run_pipeline.py")


if __name__ == "__main__":
    main()
