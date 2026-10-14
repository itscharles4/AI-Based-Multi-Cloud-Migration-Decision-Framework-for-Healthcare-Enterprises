"""
model.py
========
Defines the LSTM neural network architecture for network latency forecasting.

Architecture rationale
----------------------
- First LSTM(64, return_sequences=True):
    Learns short-term temporal patterns from the 20-step input window.
    `return_sequences=True` passes every hidden state to the next LSTM layer
    so the second layer can learn higher-level temporal abstractions.

- Dropout(0.2):
    Randomly zeros 20% of units during training to prevent over-fitting on the
    synthetic data's periodic patterns.

- Second LSTM(32, return_sequences=False):
    Compresses the temporal sequence into a single context vector (only the
    final hidden state is passed forward). 32 units keep inference fast.

- Dropout(0.2):
    Second regularisation stage.

- Dense(16, activation='relu'):
    A fully-connected bottleneck layer that learns non-linear combinations of
    the LSTM's compressed representation.

- Dense(1):
    Outputs a single scalar — the predicted current_latency_ms for the next
    time step. No activation function = linear output suitable for regression.

Loss / Optimiser
----------------
MSE loss penalises large errors more heavily than MAE, which is desirable for
latency prediction where large spikes (degradation events) are most important
to get right. Adam is used for its adaptive learning rate.
"""

try:
    from tensorflow import keras
    from tensorflow.keras import layers, Sequential
    from tensorflow.keras.optimizers import Adam
except ImportError:
    from keras import layers, Sequential
    from keras.optimizers import Adam


def build_lstm_model(window_size: int, num_features: int):
    """
    Build and compile a two-layer stacked LSTM regression model.

    Parameters
    ----------
    window_size  : int  Number of past time steps per input sample.
    num_features : int  Number of telemetry features per time step.

    Returns
    -------
    model : keras.Sequential
        Compiled Keras model ready for training.
    """
    model = Sequential(name="TelemedicineLatencyForecaster")

    # Layer 1: LSTM — captures short-term temporal dependencies
    model.add(layers.LSTM(
        units=64,
        return_sequences=True,          # pass all hidden states to the next LSTM
        input_shape=(window_size, num_features),
        name="lstm_1"
    ))
    model.add(layers.Dropout(0.2, name="dropout_1"))

    # Layer 2: LSTM — learns higher-order temporal abstractions
    model.add(layers.LSTM(
        units=32,
        return_sequences=False,         # only the final state is used downstream
        name="lstm_2"
    ))
    model.add(layers.Dropout(0.2, name="dropout_2"))

    # Fully-connected bottleneck
    model.add(layers.Dense(16, activation="relu", name="dense_relu"))

    # Output: single scalar latency value
    model.add(layers.Dense(1, name="output"))

    model.compile(
        optimizer=Adam(learning_rate=1e-3),
        loss="mse",
        metrics=["mae"],
    )

    return model


if __name__ == "__main__":
    # Quick sanity check
    model = build_lstm_model(window_size=20, num_features=5)
    model.summary()
