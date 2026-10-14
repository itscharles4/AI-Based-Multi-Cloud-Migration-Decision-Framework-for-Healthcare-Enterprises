"""
test_decision.py
================
Pytest unit tests for the Decision Layer (Tanmay's module).

Tests cover:
  1. Emergency override (criticality ≥ 9.0) always routes to EDGE
  2. Routine patient with healthy network → CLOUD
  3. Routine patient with very high latency → EDGE
  4. Borderline case returns valid dict
  5. Correct reason strings
  6. Parametrized trend test across criticality values

Run with: pytest tests/test_decision.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.decision.router import route_decision
from src.decision.ahp    import get_ahp_weights, consistency_ratio, DEFAULT_PAIRWISE_MATRIX


# ===========================================================================
# AHP sanity tests
# ===========================================================================
class TestAHP:

    def test_weights_sum_to_one(self):
        """AHP weights must normalise to 1.0."""
        weights = get_ahp_weights(DEFAULT_PAIRWISE_MATRIX)
        assert abs(sum(weights) - 1.0) < 1e-6, f"Weights sum to {sum(weights)}, expected 1.0"

    def test_weights_order(self):
        """Criticality weight > Latency weight > Cost weight."""
        w_crit, w_lat, w_cost = get_ahp_weights(DEFAULT_PAIRWISE_MATRIX)
        assert w_crit > w_lat,  "Criticality should outweigh Latency"
        assert w_lat  > w_cost, "Latency should outweigh Cost"

    def test_consistency_ratio_below_threshold(self):
        """CR < 0.10 confirms consistent pairwise matrix (AHP requirement)."""
        weights = get_ahp_weights(DEFAULT_PAIRWISE_MATRIX)
        cr      = consistency_ratio(DEFAULT_PAIRWISE_MATRIX, weights)
        assert cr < 0.10, f"Consistency Ratio {cr:.4f} exceeds 0.10 — matrix is inconsistent!"


# ===========================================================================
# Routing tests
# ===========================================================================
class TestRouteDecision:

    # ── Test 1: Emergency override always wins ────────────────────────────────
    def test_critical_patient_overrides_to_edge(self):
        """
        A patient with criticality 9.5 MUST route to EDGE even when network
        is healthy and cost is low (override fires before AHP scoring).
        """
        result = route_decision(
            device_id="ECG-101",
            patient_criticality_score=9.5,
            predicted_latency_ms=20.0,   # excellent network
            current_cloud_cost_index=0.1, # cheap cloud
        )
        assert result["routing_decision"] == "EDGE", \
            "Critical patient (9.5) must always route to EDGE"
        assert result["reason"] == "override_critical_patient"
        assert result["cloud_score"] is None, "Override path should not compute scores"
        assert result["edge_score"]  is None

    # ── Test 2: Routine patient + healthy network → CLOUD ─────────────────────
    def test_routine_patient_healthy_network_routes_cloud(self):
        """
        Low criticality + good network + cheap cloud → should prefer CLOUD.
        """
        result = route_decision(
            device_id="WEARABLE-302",
            patient_criticality_score=1.0,
            predicted_latency_ms=15.0,
            current_cloud_cost_index=0.1,
        )
        assert result["routing_decision"] == "CLOUD", \
            "Routine patient with excellent network should route to CLOUD"
        assert result["reason"] == "ahp_decision"

    # ── Test 3: Routine patient + very high latency → EDGE ───────────────────
    def test_routine_patient_high_latency_routes_edge(self):
        """
        Even routine data should go to EDGE when the network is severely
        degraded (predicted latency 450ms → cloud path is too risky).
        """
        result = route_decision(
            device_id="ECG-102",
            patient_criticality_score=1.0,
            predicted_latency_ms=450.0,   # severe degradation
            current_cloud_cost_index=0.2,
        )
        assert result["routing_decision"] == "EDGE", \
            "Very high latency (450ms) triggers network_degradation_veto and forces EDGE"
        # Reason can be either veto (veto fires at 300ms) or ahp_decision
        assert result["reason"] in {"ahp_decision", "network_degradation_veto"}

    # ── Test 4: Borderline case — just validate schema ─────────────────────
    def test_borderline_returns_valid_schema(self):
        """
        Moderate values — we don't assert direction, just that the return
        dict has all required keys and valid values.
        """
        result = route_decision(
            device_id="O2-201",
            patient_criticality_score=5.0,
            predicted_latency_ms=100.0,
            current_cloud_cost_index=0.5,
        )
        assert "device_id"        in result
        assert "routing_decision" in result
        assert "reason"           in result
        assert "cloud_score"      in result
        assert "edge_score"       in result
        assert result["routing_decision"] in {"EDGE", "CLOUD"}
        assert result["reason"] in {"ahp_decision", "override_critical_patient", "network_degradation_veto"}

    # ── Test 5: Reason string correctness ─────────────────────────────────
    def test_override_reason_string(self):
        """Override path must return exactly 'override_critical_patient'."""
        r = route_decision("ECG-101", 10.0, 50.0, 0.3)
        assert r["reason"] == "override_critical_patient"

    def test_ahp_reason_string(self):
        """Non-override, non-veto path must return exactly 'ahp_decision'."""
        r = route_decision("ECG-101", 2.0, 30.0, 0.2)  # well below 300ms veto
        assert r["reason"] == "ahp_decision"

    # ── Test 6: Parametrized trend — criticality should trend toward EDGE ──
    @pytest.mark.parametrize("criticality", [2, 4, 6, 8, 9])
    def test_routing_trend_by_criticality(self, criticality):
        """
        As patient criticality increases, routing should increasingly prefer EDGE.
        This parametrized test prints a summary table for the report.
        """
        result = route_decision(
            device_id="ECG-101",
            patient_criticality_score=float(criticality),
            predicted_latency_ms=80.0,   # moderate network
            current_cloud_cost_index=0.4,
        )
        # Basic sanity: must always return a valid decision
        assert result["routing_decision"] in {"EDGE", "CLOUD"}

        # For this moderate latency scenario, criticality >= 7 should prefer EDGE
        # (criticality 7/10 -> norm_crit=0.7, squared=0.49; at this level the
        #  AHP edge score dominates even with moderate latency)
        if criticality >= 7:
            assert result["routing_decision"] == "EDGE", \
                f"criticality={criticality} with moderate latency should route EDGE (squared AHP scoring)"

        print(
            "\n  criticality=%2d  -> %-6s  edge_score=%s  cloud_score=%s" % (
                criticality,
                result["routing_decision"],
                result.get("edge_score", "N/A"),
                result.get("cloud_score", "N/A"),
            )
        )

    # ── Test 7: Exact threshold boundary ───────────────────────────────────
    def test_override_exact_threshold(self):
        """criticality = 9.0 (exactly at threshold) must trigger override."""
        r = route_decision("ECG-101", 9.0, 200.0, 0.5)
        assert r["routing_decision"] == "EDGE"
        assert r["reason"] == "override_critical_patient"

    def test_just_below_threshold_uses_ahp(self):
        """criticality = 8.99 (just below emergency threshold) but above latency veto range."""
        r = route_decision("ECG-101", 8.99, 100.0, 0.5)  # 100ms, well below 300ms veto
        assert r["reason"] == "ahp_decision"

    def test_return_dict_has_device_id(self):
        """Returned dict must echo back the device_id correctly."""
        r = route_decision("WEARABLE-301", 3.0, 60.0, 0.3)
        assert r["device_id"] == "WEARABLE-301"
