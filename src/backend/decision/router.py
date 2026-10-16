"""
router.py
=========
Main routing decision function for the telemedicine workload offloader.

This module is intentionally a PURE PYTHON function — no AWS SDK imports,
no FastAPI imports.  This means it can be:
  - Called directly from Python (tests, local pipeline)
  - Wrapped by a thin Lambda handler with zero changes to this logic
  - Unit tested without any cloud infrastructure

AWS migration note
------------------
When deploying to AWS, create a separate lambda_handler.py that does:
  from src.decision.router import route_decision
  def lambda_handler(event, context):
      body = json.loads(event["body"])
      return route_decision(**body)

Scoring formula explained
--------------------------
After AHP weight derivation we have three weights:
  w_crit (≈0.64), w_lat (≈0.26), w_cost (≈0.10)

The routing uses two layers of logic:

Layer 1 — Hard vetoes (before AHP scoring):
  a) Emergency override: criticality ≥ 9.0 → force EDGE (clinical safety)
  b) Network degradation veto: predicted_latency_ms ≥ 300ms → force EDGE
     Rationale: at ≥300ms the cloud path is unreliable for ANY medical data;
     even routine data must be buffered locally during severe congestion.

Layer 2 — AHP scoring (when no veto fires):
  EDGE score  = w_crit * norm_criticality^2  (square amplifies high criticality)
              + w_lat  * norm_latency          (high latency → edge)
              + w_cost * norm_cost

  CLOUD score = w_crit * (1-norm_criticality)^2
              + w_lat  * (1-norm_latency)
              + w_cost * (1-norm_cost)

  Whichever score is higher determines routing (reason = "ahp_decision").
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.decision.ahp            import get_ahp_weights, normalize_criteria, DEFAULT_PAIRWISE_MATRIX
from src.decision.override_rules import check_emergency_override


def route_decision(
    device_id:                  str,
    patient_criticality_score:  float,
    predicted_latency_ms:       float,
    current_cloud_cost_index:   float,
) -> dict:
    """
    Make an edge-vs-cloud routing decision for a single telemetry event.

    Parameters
    ----------
    device_id                 : str    Device identifier (e.g. "ECG-101").
    patient_criticality_score : float  0–10 scale; 10 = cardiac arrest.
    predicted_latency_ms      : float  LSTM-predicted network latency in ms.
    current_cloud_cost_index  : float  0–1 normalised cloud cost/load index.

    Returns
    -------
    dict with keys:
        device_id         : str
        routing_decision  : "EDGE" | "CLOUD"
        reason            : "override_critical_patient" | "ahp_decision"
        cloud_score       : float | None  (None if override fired)
        edge_score        : float | None  (None if override fired)
    """
    # ── Step 1: Emergency override check (clinical safety veto) ─────────────
    if check_emergency_override(patient_criticality_score):
        return {
            "device_id":        device_id,
            "routing_decision": "EDGE",
            "reason":           "override_critical_patient",
            "cloud_score":      None,
            "edge_score":       None,
        }

    # ── Step 1b: Network degradation veto ────────────────────────────────────
    # At predicted_latency ≥ 300ms the cloud path is unreliable for ANY
    # medical data.  Even routine data must be buffered locally during
    # severe network congestion.  This is the "prediction instead of reaction"
    # novelty — we veto BEFORE routing, not after a timeout.
    LATENCY_VETO_MS = 300.0
    if predicted_latency_ms >= LATENCY_VETO_MS:
        return {
            "device_id":        device_id,
            "routing_decision": "EDGE",
            "reason":           "network_degradation_veto",
            "cloud_score":      None,
            "edge_score":       None,
        }

    # ── Step 2: Derive AHP weights ────────────────────────────────────────────
    weights = get_ahp_weights(DEFAULT_PAIRWISE_MATRIX)
    w_crit, w_lat, w_cost = weights[0], weights[1], weights[2]

    # ── Step 3: Normalise inputs to [0, 1] ───────────────────────────────────
    norm_crit, norm_lat, norm_cost = normalize_criteria(
        patient_criticality_score,
        predicted_latency_ms,
        current_cloud_cost_index,
    )

    # ── Step 4: Compute weighted scores ──────────────────────────────────────
    #
    # EDGE score: rises when criticality is HIGH, latency is HIGH, cost is HIGH.
    #   - norm_crit is SQUARED so that mid-to-high criticality (0.6+) clearly
    #     dominates; low criticality (0.1) contributes very little.
    #   - This ensures that a patient with score 6/10 gets routed to EDGE
    #     even at moderate latency — protecting patients who are "serious but
    #     not yet Code Blue".
    edge_score  = (w_crit * (norm_crit ** 2)
                 + w_lat  * norm_lat
                 + w_cost * norm_cost)

    # CLOUD score: symmetric inverse — low criticality and low latency
    # both favour the cheaper cloud path.
    cloud_score = (w_crit * ((1.0 - norm_crit) ** 2)
                 + w_lat  * (1.0 - norm_lat)
                 + w_cost * (1.0 - norm_cost))

    # ── Step 5: Pick the higher score ────────────────────────────────────────
    routing_decision = "EDGE" if edge_score >= cloud_score else "CLOUD"
    reason           = "ahp_decision"

    return {
        "device_id":        device_id,
        "routing_decision": routing_decision,
        "reason":           reason,
        "cloud_score":      round(cloud_score, 4),
        "edge_score":       round(edge_score,  4),
    }


if __name__ == "__main__":
    # Quick demo
    scenarios = [
        ("ECG-101", 9.5, 210.5, 0.4),   # Critical patient → override
        ("ECG-102", 1.0, 20.0,  0.2),   # Routine, good network → cloud
        ("O2-201",  5.0, 300.0, 0.5),   # Moderate, high latency → edge?
        ("WEARABLE-301", 7.0, 80.0, 0.7),  # High criticality, moderate latency
    ]

    print(f"{'Device':<16} {'Crit':>6} {'Lat':>8} {'Cost':>6} → {'Decision':<8} {'Reason'}")
    print("-" * 75)
    for args in scenarios:
        result = route_decision(*args)
        print(
            f"{result['device_id']:<16}"
            f" {args[1]:>6.1f}"
            f" {args[2]:>8.1f}ms"
            f" {args[3]:>6.2f}"
            f" → {result['routing_decision']:<8}"
            f" {result['reason']}"
        )
