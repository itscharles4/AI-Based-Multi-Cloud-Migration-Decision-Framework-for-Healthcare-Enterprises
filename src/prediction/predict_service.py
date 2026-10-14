"""
predict_service.py
==================
Inference service for the LSTM latency forecasting model.

Public API
----------
  predict_latency(window: list[dict]) -> dict

The model and scaler are loaded ONCE at module import time for performance.
On AWS migration this becomes a thin wrapper around boto3.invoke_endpoint()
to a SageMaker hosted endpoint — the function signature and return dict
shape remain unchanged.

Network Degradation Risk Classification
----------------------------------------
  predicted_latency_ms < 75   → "LOW"
  75 ≤ predicted_latency_ms < 150 → "MEDIUM"
  predicted_latency_ms ≥ 150  → "HIGH"
"""

import os
import sys
import numpy as np
import joblib

# Resolve project root so this file can be run from any directory
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

MODEL_PATH  = os.path.join(_HERE, "model.h5")
SCALER_PATH = os.path.join(_ROOT, "data", "processed", "scaler.pkl")

WINDOW_SIZE  = 20
FEATURE_COLS = [
    "bandwidth_mbps",
    "packet_loss_pct",
    "jitter_ms",
    "signal_strength_dbm",
    "current_latency_ms",
]

# ---------------------------------------------------------------------------
# Load model & scaler once at import time (not per-call)
# ---------------------------------------------------------------------------
def _load_model():
    """Load Keras model, gracefully return None if model file is missing."""
    try:
        try:
            from tensorflow.keras.models import load_model as keras_load
        except ImportError:
            from keras.models import load_model as keras_load
        if os.path.exists(MODEL_PATH):
            return keras_load(MODEL_PATH)
        else:
            print(f"[predict_service] WARNING: model.h5 not found at {MODEL_PATH}. "
                  "Run train.py first. Using dummy predictions.")
            return None
    except Exception as e:
        print(f"[predict_service] WARNING: Could not load model — {e}. Using dummy predictions.")
        return None


def _load_scaler():
    """Load fitted MinMaxScaler from disk."""
    if os.path.exists(SCALER_PATH):
        return joblib.load(SCALER_PATH)
    print(f"[predict_service] WARNING: scaler.pkl not found at {SCALER_PATH}. "
          "Run preprocessing.py first.")
    return None


_MODEL  = _load_model()
_SCALER = _load_scaler()


# ---------------------------------------------------------------------------
# Public inference function
# ---------------------------------------------------------------------------
def predict_latency(window: list) -> dict:
    """
    Predict network latency and degradation risk for a rolling telemetry window.

    Parameters
    ----------
    window : list[dict]
        Exactly 20 telemetry dicts, ordered oldest → newest.
        Each dict must contain at minimum the keys in FEATURE_COLS plus 'device_id'.

    Returns
    -------
    dict with keys:
        device_id               : str   — from the last item in window
        predicted_latency_ms    : float — back-transformed to real milliseconds
        network_degradation_risk: str   — "LOW" | "MEDIUM" | "HIGH"
        forecast_horizon_seconds: int   — always 30
    """
    if len(window) != WINDOW_SIZE:
        raise ValueError(f"predict_latency() requires exactly {WINDOW_SIZE} records, got {len(window)}.")

    device_id = window[-1].get("device_id", "UNKNOWN")

    # --- Extract numeric features in training column order ---
    raw = np.array(
        [[record[col] for col in FEATURE_COLS] for record in window],
        dtype=np.float32
    )  # shape: (20, 5)

    # --- Scale using the fitted scaler ---
    if _SCALER is not None:
        scaled = _SCALER.transform(raw)   # shape: (20, 5)
    else:
        # Fallback: no scaler — use raw values (predictions will be unreliable)
        scaled = raw

    X = scaled.reshape(1, WINDOW_SIZE, len(FEATURE_COLS))  # (1, 20, 5)

    # --- Run model inference ---
    if _MODEL is not None:
        pred_scaled = float(_MODEL.predict(X, verbose=0).flatten()[0])

        # Inverse-transform: only need to invert the latency column
        # Scaler was fit on all 5 features; we create a dummy row for inverse
        dummy = np.zeros((1, len(FEATURE_COLS)), dtype=np.float32)
        latency_idx = FEATURE_COLS.index("current_latency_ms")
        dummy[0, latency_idx] = pred_scaled
        pred_ms = float(_SCALER.inverse_transform(dummy)[0, latency_idx])
    else:
        # No model: simulate based on last raw latency value
        pred_ms = float(window[-1].get("current_latency_ms", 50.0)) * 1.1

    pred_ms = max(0.0, pred_ms)

    # --- Classify risk ---
    if pred_ms < 75:
        risk = "LOW"
    elif pred_ms < 150:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    return {
        "device_id":                device_id,
        "predicted_latency_ms":     round(pred_ms, 2),
        "network_degradation_risk": risk,
        "forecast_horizon_seconds": 30,
    }


# ---------------------------------------------------------------------------
# Quick manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import random
    # Build a dummy window of 20 records
    dummy_window = [
        {
            "device_id":           "ECG-101",
            "bandwidth_mbps":      random.uniform(30, 100),
            "packet_loss_pct":     random.uniform(0, 2),
            "jitter_ms":           random.uniform(2, 15),
            "signal_strength_dbm": random.uniform(-80, -50),
            "current_latency_ms":  random.uniform(10, 50),
        }
        for _ in range(20)
    ]

    result = predict_latency(dummy_window)
    print("[predict_service] Demo prediction result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
