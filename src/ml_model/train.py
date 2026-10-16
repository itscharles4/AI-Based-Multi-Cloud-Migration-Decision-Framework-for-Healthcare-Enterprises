"""
train.py
========
Training script for the LSTM latency forecasting model.
Designed to run locally or in Google Colab (CPU or GPU).

Usage
-----
  python train.py
  # or in Colab: !python train.py

Outputs
-------
  src/prediction/model.h5          — saved trained model
  results/graphs/training_loss.png — training + validation loss curves
  results/graphs/pred_vs_actual.png — predicted vs actual latency on test set
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Allow running from anywhere in the project tree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
except ImportError:
    import tensorflow as tf
    from keras.callbacks import EarlyStopping, ModelCheckpoint

from src.prediction.model import build_lstm_model

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSED_DIR = os.path.join("data", "processed")
GRAPHS_DIR    = os.path.join("results", "graphs")
MODEL_OUT     = os.path.join("src", "prediction", "model.h5")

os.makedirs(GRAPHS_DIR, exist_ok=True)


def load_data():
    """Load pre-built .npy arrays from preprocessing step."""
    X_train = np.load(os.path.join(PROCESSED_DIR, "X_train.npy"))
    y_train = np.load(os.path.join(PROCESSED_DIR, "y_train.npy"))
    X_test  = np.load(os.path.join(PROCESSED_DIR, "X_test.npy"))
    y_test  = np.load(os.path.join(PROCESSED_DIR, "y_test.npy"))
    return X_train, X_test, y_train, y_test


def plot_training_loss(history, out_path: str):
    """Save training + validation MSE loss curve."""
    plt.figure(figsize=(10, 5))
    plt.plot(history.history["loss"],     label="Train Loss (MSE)", linewidth=2)
    plt.plot(history.history["val_loss"], label="Val Loss (MSE)",   linewidth=2, linestyle="--")
    plt.title("LSTM Training Loss — Network Latency Forecasting", fontsize=14)
    plt.xlabel("Epoch")
    plt.ylabel("Mean Squared Error")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"[train] Training loss curve saved → {out_path}")


def plot_pred_vs_actual(y_true: np.ndarray, y_pred: np.ndarray, out_path: str):
    """Save predicted-vs-actual latency line chart on test set."""
    # Show only first 500 samples for clarity
    n = min(500, len(y_true))
    plt.figure(figsize=(14, 5))
    plt.plot(y_true[:n], label="Actual Latency (scaled)",    linewidth=1.5, color="#2196F3")
    plt.plot(y_pred[:n], label="Predicted Latency (scaled)", linewidth=1.5, color="#FF5722", linestyle="--")
    plt.title("Predicted vs Actual Network Latency — Test Set (first 500 samples)", fontsize=14)
    plt.xlabel("Time Step")
    plt.ylabel("Latency (MinMax scaled)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"[train] Predicted vs actual chart saved → {out_path}")


def main():
    print("[train] Loading data...")
    X_train, X_test, y_train, y_test = load_data()

    window_size  = X_train.shape[1]
    num_features = X_train.shape[2]
    print(f"[train] X_train shape: {X_train.shape}  |  window_size={window_size}, num_features={num_features}")

    # --- Build model ---
    model = build_lstm_model(window_size=window_size, num_features=num_features)
    model.summary()

    # --- Callbacks ---
    early_stop = EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True,
        verbose=1
    )
    checkpoint = ModelCheckpoint(
        filepath=MODEL_OUT,
        monitor="val_loss",
        save_best_only=True,
        verbose=1
    )

    # --- Train ---
    print("\n[train] Starting training (up to 50 epochs, EarlyStopping patience=5)...")
    history = model.fit(
        X_train, y_train,
        epochs=50,
        batch_size=32,
        validation_split=0.1,
        callbacks=[early_stop, checkpoint],
        verbose=1,
    )

    # --- Evaluate ---
    print("\n[train] Evaluating on test set...")
    test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)
    test_rmse = np.sqrt(test_loss)

    print(f"\n{'='*55}")
    print(f"| Metric              | Value                      |")
    print(f"{'='*55}")
    print(f"| Test MAE  (scaled)  | {test_mae:.6f}                 |")
    print(f"| Test RMSE (scaled)  | {test_rmse:.6f}                 |")
    print(f"| Epochs run          | {len(history.history['loss']):>6}                      |")
    print(f"{'='*55}")

    # --- Generate graphs ---
    y_pred = model.predict(X_test).flatten()
    plot_training_loss(history, os.path.join(GRAPHS_DIR, "training_loss.png"))
    plot_pred_vs_actual(y_test, y_pred, os.path.join(GRAPHS_DIR, "pred_vs_actual.png"))

    print(f"\n[train] Model saved → {MODEL_OUT}")
    print("[train] Done. Paste the metrics table above into the report.")


if __name__ == "__main__":
    main()
