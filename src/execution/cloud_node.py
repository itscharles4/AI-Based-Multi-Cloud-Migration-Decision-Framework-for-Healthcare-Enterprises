# TODO AWS MIGRATION: this becomes an AWS Lambda function reading from the main cloud pipeline / API Gateway
"""
cloud_node.py
=============
Simulates cloud-side processing for routine telemetry data, standing in for
the "route to cloud" execution path in the AWS architecture.

When a routing decision of "CLOUD" is made, this module:
  - Does NOT trigger any local alert (this is routine/non-critical data).
  - Persists the event to hot and cold storage for analytics.
  - Logs the event via the structured logger.

On AWS migration
----------------
  This file's handle_event() becomes a standard AWS Lambda function.
  It would be triggered by API Gateway (or an SQS queue) instead of being
  called directly from the FastAPI pipeline.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.execution import storage, logger


def handle_event(event: dict) -> dict:
    """
    Process a telemedicine event routed to the cloud node.

    Parameters
    ----------
    event : dict
        Must contain: device_id, routing_decision, reason,
        patient_criticality_score, predicted_latency_ms, timestamp.
        May optionally contain: raw_payload (dict of raw telemetry).

    Returns
    -------
    dict  {"status": "processed_in_cloud", "device_id": ..., "alerted": False}
    """
    device_id   = event.get("device_id",  "UNKNOWN")
    timestamp   = event.get("timestamp",  "")
    raw_payload = event.get("raw_payload", None)

    # ── Hot storage (simulates DynamoDB) ─────────────────────────────────────
    storage.init_db()
    storage.save_hot({
        "device_id":                 device_id,
        "timestamp":                 timestamp,
        "routing_decision":          event.get("routing_decision", "CLOUD"),
        "reason":                    event.get("reason", "unknown"),
        "predicted_latency_ms":      event.get("predicted_latency_ms", 0.0),
        "patient_criticality_score": event.get("patient_criticality_score", 0.0),
    })

    # ── Cold storage (simulates S3) — archive raw payload if available ────────
    if raw_payload:
        storage.save_cold(device_id, timestamp, raw_payload)

    # ── Structured log (simulates CloudWatch) ────────────────────────────────
    logger.log_event("CLOUD_PROCESSED", {
        **event,
        "alerted": False,
    })

    return {
        "status":    "processed_in_cloud",
        "device_id": device_id,
        "alerted":   False,
    }


if __name__ == "__main__":
    test_event = {
        "device_id":                 "WEARABLE-301",
        "routing_decision":          "CLOUD",
        "reason":                    "ahp_decision",
        "patient_criticality_score": 1.5,
        "predicted_latency_ms":      22.3,
        "timestamp":                 "2026-09-22T10:16:00Z",
        "raw_payload": {
            "bandwidth_mbps":      68.5,
            "packet_loss_pct":     0.3,
            "jitter_ms":           5.2,
            "signal_strength_dbm": -59,
            "current_latency_ms":  18.0,
        },
    }
    result = handle_event(test_event)
    print("Cloud node result:", result)
