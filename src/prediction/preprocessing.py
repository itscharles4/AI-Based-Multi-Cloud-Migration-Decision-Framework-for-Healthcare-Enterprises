"""
preprocessing.py
================
Loads the raw telemetry CSV, applies Min-Max scaling, builds sliding-window
sequences for time-series modelling, and saves train/test splits as .npy files.

Expected input : data/raw/telemetry_data.csv
Outputs        :
  data/processed/scaler.pkl   — fitted MinMaxScaler (needed for inference)
  data/processed/X_train.npy  — (num_samples, window_size, num_features)
  data/processed/y_train.npy  — (num_samples,)
  data/processed/X_test.npy
  data/processed/y_test.npy
"""

import os
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import MinMaxScaler

# Features used as model inputs (in this exact column order)
FEATURE_COLS = [
    "bandwidth_mbps",
    "packet_loss_pct",
    "jitter_ms",
    "signal_strength_dbm",
    "current_latency_ms",
]
TARGET_COL = "current_latency_ms"


def build_sliding_windows(data: np.ndarray, window_size: int):
    """
    Convert a 2-D array (time_steps x features) into overlapping sliding windows.

    Each window uses `window_size` past readings as input (X) and the
    target column value of the *next* reading as the label (y).

    Parameters
    ----------
    data : np.ndarray, shape (T, F)
        Scaled feature matrix for a single device, sorted by time.
    window_size : int
        Number of past time steps per input sequence.

    Returns
    -------
    X : np.ndarray, shape (num_windows, window_size, F)
    y : np.ndarray, shape (num_windows,)
    """
    X, y = [], []
    # Target column index (current_latency_ms is the last column after scaling)
    target_idx = FEATURE_COLS.index(TARGET_COL)

    for i in range(window_size, len(data)):
        X.append(data[i - window_size: i, :])   # past `window_size` readings
        y.append(data[i, target_idx])            # next reading's latency

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def build_dataset(
    csv_path: str = os.path.join("data", "raw", "telemetry_data.csv"),
    window_size: int = 20,
):
    """
    Full preprocessing pipeline:
      1. Load & sort CSV
      2. Fit MinMaxScaler on training portion, transform all data
      3. Build per-device sliding windows
      4. Concatenate, split 80/20 (preserving time order), save .npy files

    Parameters
    ----------
    csv_path   : str   Path to the raw telemetry CSV.
    window_size: int   Number of past readings per input window (default 20).

    Returns
    -------
    X_train, X_test, y_train, y_test : np.ndarray
    """
    print(f"[preprocessing] Loading {csv_path}...")
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["device_id", "timestamp"]).reset_index(drop=True)

    # --- Fit scaler on the first 80% of each device's data (no leakage) ---
    # We fit on the full training portion across all devices.
    all_X, all_y = [], []

    devices = df["device_id"].unique()
    numeric_df = df[FEATURE_COLS].values  # shape (N, num_features)

    # Fit scaler on 80% of the full dataset (sorted by device+time, no shuffling)
    split_at   = int(len(numeric_df) * 0.8)
    scaler     = MinMaxScaler()
    scaler.fit(numeric_df[:split_at])

    scaled_all = scaler.transform(numeric_df)  # scale entire dataset

    # Re-attach scaled values to dataframe for per-device windowing
    df_scaled = df.copy()
    df_scaled[FEATURE_COLS] = scaled_all

    for device_id in devices:
        device_data = df_scaled[df_scaled["device_id"] == device_id][FEATURE_COLS].values
        X_dev, y_dev = build_sliding_windows(device_data, window_size)
        all_X.append(X_dev)
        all_y.append(y_dev)

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y, axis=0)

    # --- 80/20 split, non-shuffled (preserve temporal order) ---
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    # --- Save everything ---
    out_dir = os.path.join("data", "processed")
    os.makedirs(out_dir, exist_ok=True)

    joblib.dump(scaler, os.path.join(out_dir, "scaler.pkl"))
    np.save(os.path.join(out_dir, "X_train.npy"), X_train)
    np.save(os.path.join(out_dir, "y_train.npy"), y_train)
    np.save(os.path.join(out_dir, "X_test.npy"),  X_test)
    np.save(os.path.join(out_dir, "y_test.npy"),  y_test)

    print(f"[preprocessing] X_train: {X_train.shape}  y_train: {y_train.shape}")
    print(f"[preprocessing] X_test : {X_test.shape}   y_test : {y_test.shape}")
    print(f"[preprocessing] Scaler saved to {out_dir}/scaler.pkl")

    return X_train, X_test, y_train, y_test


if __name__ == "__main__":
    build_dataset()
