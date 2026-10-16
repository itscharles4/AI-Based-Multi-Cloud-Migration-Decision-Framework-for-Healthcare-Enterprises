"""
data_generator.py
=================
Generates a synthetic dataset simulating hospital IoMT (Internet of Medical Things)
network telemetry for time-series forecasting.

Devices: ECG-101, ECG-102, O2-201, WEARABLE-301, WEARABLE-302
Rows:    20,000 rows at 1-second intervals (configurable via CLI)
Output:  data/raw/telemetry_data.csv
"""

import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

# ---------------------------------------------------------------------------
# Constants — normal operating ranges
# ---------------------------------------------------------------------------
NORMAL_BANDWIDTH_MEAN = 60.0        # Mbps
NORMAL_BANDWIDTH_STD  = 10.0
NORMAL_PACKET_LOSS_MEAN = 0.5       # percent
NORMAL_PACKET_LOSS_STD  = 0.3
NORMAL_JITTER_MEAN = 6.0            # ms
NORMAL_JITTER_STD  = 2.0
NORMAL_SIGNAL_MEAN = -65.0          # dBm
NORMAL_SIGNAL_STD  = 5.0
NORMAL_LATENCY_MEAN = 25.0          # ms
NORMAL_LATENCY_STD  = 8.0


def _clamp(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Utility: clamp array values between lo and hi."""
    return np.clip(arr, lo, hi)


def inject_degradation_events(df: pd.DataFrame, degradation_pct: float = 0.05) -> pd.DataFrame:
    """
    Inject realistic network degradation events into the telemetry dataframe.

    Degradation events simulate sudden congestion or connectivity problems:
      - Bandwidth drops sharply
      - Packet loss spikes
      - Jitter rises dramatically
      - Latency spikes to 150-400 ms

    Transitions into and out of a degradation event are gradual (ramped),
    not instantaneous, to reflect real-world network behaviour.

    Parameters
    ----------
    df : pd.DataFrame
        Telemetry dataframe with numeric columns (already sorted by device & time).
    degradation_pct : float
        Fraction of total time windows to mark as degraded (~5%).

    Returns
    -------
    pd.DataFrame
        Modified dataframe with degradation events injected.
    """
    n = len(df)
    total_windows = int(n * degradation_pct)
    already_degraded = np.zeros(n, dtype=bool)

    for _ in range(total_windows):
        # Pick a random start index and event duration (10-60 seconds)
        start_idx = np.random.randint(0, n - 60)
        duration  = np.random.randint(10, 61)
        end_idx   = min(start_idx + duration, n - 1)

        # Skip if this window overlaps an existing degradation event
        if already_degraded[start_idx:end_idx + 1].any():
            continue

        already_degraded[start_idx:end_idx + 1] = True

        # Build a ramp profile: 0→1 over first 20%, flat at 1, then 1→0 over last 20%
        seg_len   = end_idx - start_idx + 1
        ramp_len  = max(1, int(seg_len * 0.2))
        ramp_up   = np.linspace(0, 1, ramp_len)
        ramp_down = np.linspace(1, 0, ramp_len)
        flat_len  = max(0, seg_len - 2 * ramp_len)
        profile   = np.concatenate([ramp_up, np.ones(flat_len), ramp_down])
        profile   = profile[:seg_len]  # ensure exact length

        indices = slice(start_idx, end_idx + 1)

        # Apply degraded values blended with normal values via the ramp profile
        degraded_bw       = np.random.uniform(5, 20, seg_len)
        degraded_loss     = np.random.uniform(5, 20, seg_len)
        degraded_jitter   = np.random.uniform(30, 100, seg_len)
        degraded_latency  = np.random.uniform(150, 400, seg_len)

        df.loc[df.index[indices], "bandwidth_mbps"]   = (
            df.loc[df.index[indices], "bandwidth_mbps"].values * (1 - profile)
            + degraded_bw * profile
        )
        df.loc[df.index[indices], "packet_loss_pct"]  = (
            df.loc[df.index[indices], "packet_loss_pct"].values * (1 - profile)
            + degraded_loss * profile
        )
        df.loc[df.index[indices], "jitter_ms"]        = (
            df.loc[df.index[indices], "jitter_ms"].values * (1 - profile)
            + degraded_jitter * profile
        )
        df.loc[df.index[indices], "current_latency_ms"] = (
            df.loc[df.index[indices], "current_latency_ms"].values * (1 - profile)
            + degraded_latency * profile
        )

    return df


def generate_telemetry(num_rows: int = 20000, devices: list = None) -> pd.DataFrame:
    """
    Generate synthetic IoMT telemetry with injected degradation events.

    Parameters
    ----------
    num_rows : int
        Total number of rows across all devices.
    devices : list[str]
        List of device IDs.

    Returns
    -------
    pd.DataFrame
        Full telemetry dataframe ready to be saved to CSV.
    """
    if devices is None:
        devices = ["ECG-101", "ECG-102", "O2-201", "WEARABLE-301", "WEARABLE-302"]

    rows_per_device = num_rows // len(devices)
    start_time      = datetime(2026, 9, 1, 0, 0, 0)
    all_dfs         = []

    rng = np.random.default_rng(seed=42)

    for device_id in devices:
        timestamps = [start_time + timedelta(seconds=i) for i in range(rows_per_device)]

        # --- Generate normal baseline values ---
        bandwidth   = _clamp(rng.normal(NORMAL_BANDWIDTH_MEAN, NORMAL_BANDWIDTH_STD, rows_per_device),   30, 100)
        packet_loss = _clamp(rng.normal(NORMAL_PACKET_LOSS_MEAN, NORMAL_PACKET_LOSS_STD, rows_per_device), 0, 2)
        jitter      = _clamp(rng.normal(NORMAL_JITTER_MEAN, NORMAL_JITTER_STD, rows_per_device),           2, 15)
        signal      = _clamp(rng.normal(NORMAL_SIGNAL_MEAN, NORMAL_SIGNAL_STD, rows_per_device),         -80, -50)
        latency     = _clamp(rng.normal(NORMAL_LATENCY_MEAN, NORMAL_LATENCY_STD, rows_per_device),        10, 50)

        device_df = pd.DataFrame({
            "timestamp":           [ts.isoformat() + "Z" for ts in timestamps],
            "device_id":           device_id,
            "bandwidth_mbps":      bandwidth,
            "packet_loss_pct":     packet_loss,
            "jitter_ms":           jitter,
            "signal_strength_dbm": signal,
            "current_latency_ms":  latency,
        })

        # --- Inject degradation events ---
        device_df = inject_degradation_events(device_df, degradation_pct=0.05)

        all_dfs.append(device_df)

    full_df = pd.concat(all_dfs, ignore_index=True)

    # Round floats to 2 decimal places for readability
    for col in ["bandwidth_mbps", "packet_loss_pct", "jitter_ms", "current_latency_ms"]:
        full_df[col] = full_df[col].round(2)
    full_df["signal_strength_dbm"] = full_df["signal_strength_dbm"].round(1)

    return full_df


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic IoMT telemetry dataset for the telemedicine project."
    )
    parser.add_argument("--rows",    type=int, default=20000, help="Total number of rows to generate (default: 20000)")
    parser.add_argument("--devices", type=str, default=None,  help="Comma-separated list of device IDs (default: 5 built-in devices)")
    args = parser.parse_args()

    devices = args.devices.split(",") if args.devices else None
    print(f"[data_generator] Generating {args.rows} rows across {len(devices) if devices else 5} devices...")

    df = generate_telemetry(num_rows=args.rows, devices=devices)

    output_path = os.path.join("data", "raw", "telemetry_data.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"[data_generator] Saved {len(df)} rows to {output_path}")
    print(df.describe())


if __name__ == "__main__":
    main()
