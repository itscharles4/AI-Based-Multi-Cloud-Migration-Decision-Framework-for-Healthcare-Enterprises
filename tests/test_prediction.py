"""
test_prediction.py
==================
Pytest unit tests for the Prediction Layer (Charles's module).

Tests cover:
  1. predict_latency() returns correct schema keys
  2. Risk classification thresholds (LOW/MEDIUM/HIGH)
  3. Window size validation (exactly 20 records required)
  4. Dummy-mode (no model.h5) returns a valid dict
  5. Correct device_id echoed back
  6. Forecast horizon is always 30 seconds

Run with: pytest tests/test_prediction.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.prediction.predict_service import predict_latency, WINDOW_SIZE, FEATURE_COLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_window(device_id="ECG-101", latency_ms=30.0, bandwidth=60.0,
                 packet_loss=0.5, jitter=6.0, signal=-65.0, size=None):
    """Build a synthetic telemetry window."""
    if size is None:
        size = WINDOW_SIZE
    return [
        {
            "device_id":           device_id,
            "bandwidth_mbps":      bandwidth,
            "packet_loss_pct":     packet_loss,
            "jitter_ms":           jitter,
            "signal_strength_dbm": signal,
            "current_latency_ms":  latency_ms,
        }
        for _ in range(size)
    ]


# ===========================================================================
# Schema / return structure tests
# ===========================================================================
class TestPredictLatencySchema:

    def test_returns_dict(self):
        """predict_latency() must return a dict."""
        result = predict_latency(_make_window())
        assert isinstance(result, dict)

    def test_required_keys_present(self):
        """Result must contain all four required keys."""
        result = predict_latency(_make_window())
        required_keys = {"device_id", "predicted_latency_ms",
                         "network_degradation_risk", "forecast_horizon_seconds"}
        assert required_keys.issubset(result.keys()), \
            f"Missing keys: {required_keys - result.keys()}"

    def test_device_id_echoed_correctly(self):
        """device_id from the last window record should be echoed back."""
        result = predict_latency(_make_window(device_id="O2-201"))
        assert result["device_id"] == "O2-201"

    def test_forecast_horizon_always_30(self):
        """forecast_horizon_seconds must always equal 30."""
        result = predict_latency(_make_window())
        assert result["forecast_horizon_seconds"] == 30

    def test_predicted_latency_is_non_negative(self):
        """Predicted latency (ms) must be >= 0."""
        result = predict_latency(_make_window())
        assert result["predicted_latency_ms"] >= 0.0

    def test_predicted_latency_is_numeric(self):
        """predicted_latency_ms must be a numeric type."""
        result = predict_latency(_make_window())
        assert isinstance(result["predicted_latency_ms"], (int, float))


# ===========================================================================
# Risk classification threshold tests
# ===========================================================================
class TestRiskClassification:
    """
    Risk levels (from predict_service.py docstring):
      predicted_latency_ms < 75    -> "LOW"
      75 <= predicted_latency_ms < 150 -> "MEDIUM"
      predicted_latency_ms >= 150  -> "HIGH"

    Without a trained model, the service falls back to:
      pred_ms = last record's current_latency_ms * 1.1
    We exploit that fallback to deterministically test classification.
    """

    def _risk_for_latency(self, raw_latency):
        window = _make_window(latency_ms=raw_latency)
        return predict_latency(window)["network_degradation_risk"]

    def test_risk_classification_low(self):
        """Fallback prediction < 75ms must be LOW risk."""
        # 30 * 1.1 = 33ms -> LOW
        risk = self._risk_for_latency(30.0)
        assert risk == "LOW", f"Expected LOW, got {risk}"

    def test_risk_classification_medium_boundary(self):
        """Fallback prediction in 75-149ms range must be MEDIUM risk."""
        # 70 * 1.1 = 77ms -> MEDIUM
        risk = self._risk_for_latency(70.0)
        assert risk == "MEDIUM", f"Expected MEDIUM, got {risk}"

    def test_risk_classification_high(self):
        """Fallback prediction >= 150ms must be HIGH risk."""
        # 140 * 1.1 = 154ms -> HIGH
        risk = self._risk_for_latency(140.0)
        assert risk == "HIGH", f"Expected HIGH, got {risk}"

    def test_risk_values_are_valid_strings(self):
        """network_degradation_risk must always be LOW, MEDIUM, or HIGH."""
        for latency in [10.0, 50.0, 80.0, 140.0, 200.0]:
            result = predict_latency(_make_window(latency_ms=latency))
            assert result["network_degradation_risk"] in {"LOW", "MEDIUM", "HIGH"}

    @pytest.mark.parametrize("raw_lat,expected_risk", [
        (5.0,   "LOW"),    # 5.0 * 1.1 = 5.5ms
        (30.0,  "LOW"),    # 30  * 1.1 = 33ms
        (70.0,  "MEDIUM"), # 70  * 1.1 = 77ms
        (100.0, "MEDIUM"), # 100 * 1.1 = 110ms
        (140.0, "HIGH"),   # 140 * 1.1 = 154ms
        (200.0, "HIGH"),   # 200 * 1.1 = 220ms
    ])
    def test_risk_parametrized(self, raw_lat, expected_risk):
        """Parametrized fallback-based risk classification table."""
        risk = self._risk_for_latency(raw_lat)
        assert risk == expected_risk, \
            f"raw_lat={raw_lat}ms -> expected {expected_risk}, got {risk}"


# ===========================================================================
# Window size validation
# ===========================================================================
class TestWindowSizeValidation:

    def test_raises_value_error_for_short_window(self):
        """Window with fewer than 20 records must raise ValueError."""
        with pytest.raises(ValueError):
            predict_latency(_make_window(size=10))

    def test_raises_value_error_for_long_window(self):
        """Window with more than 20 records must raise ValueError."""
        with pytest.raises(ValueError):
            predict_latency(_make_window(size=25))

    def test_accepts_exactly_20_records(self):
        """Window with exactly 20 records must NOT raise any exception."""
        try:
            predict_latency(_make_window(size=20))
        except ValueError:
            pytest.fail("predict_latency() raised ValueError for a valid 20-record window")

    def test_error_message_mentions_window_size(self):
        """ValueError message should mention the required window size."""
        with pytest.raises(ValueError, match=str(WINDOW_SIZE)):
            predict_latency(_make_window(size=5))


# ===========================================================================
# Feature column validation
# ===========================================================================
class TestFeatureColumns:

    def test_feature_cols_count(self):
        """FEATURE_COLS must have exactly 5 entries."""
        assert len(FEATURE_COLS) == 5, f"Expected 5 feature cols, found {len(FEATURE_COLS)}"

    def test_feature_cols_contains_latency(self):
        """current_latency_ms must be in FEATURE_COLS (it is the target)."""
        assert "current_latency_ms" in FEATURE_COLS

    @pytest.mark.parametrize("col", [
        "bandwidth_mbps",
        "packet_loss_pct",
        "jitter_ms",
        "signal_strength_dbm",
        "current_latency_ms",
    ])
    def test_all_expected_feature_cols_present(self, col):
        """Each expected feature column must be in FEATURE_COLS."""
        assert col in FEATURE_COLS, f"'{col}' not found in FEATURE_COLS"
