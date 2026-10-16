# TODO AWS MIGRATION: this becomes the AWS IoT Greengrass local Lambda function
"""
edge_node.py
============
Simulates local hospital edge processing, standing in for AWS IoT Greengrass.

When a routing decision of "EDGE" is made, this module:
  1. Triggers a LOCAL ALERT (simulating paging the on-call doctor via SNS locally)
  2. Persists the event to hot storage (DynamoDB sim)
  3. Archives the raw payload to cold storage (S3 sim)
  4. Logs everything via the structured logger (CloudWatch sim)

On AWS migration
----------------
  This file's handle_event() becomes the Greengrass local Lambda function body.
  The SNS alert line becomes: boto3.client('sns').publish(...)
  Storage calls become the DynamoDB/S3 boto3 equivalents.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.execution import storage, logger


def handle_event(event: dict) -> dict:
    """
    Process a telemedicine event routed to the local edge node.

    Parameters
    ----------
    event : dict
        Must contain: device_id, routing_decision, reason,
        patient_criticality_score, predicted_latency_ms, timestamp.
        May optionally contain: raw_payload (dict of raw telemetry).

    Returns
    -------
    dict  {"status": "processed_at_edge", "device_id": ..., "alerted": True}
    """
    device_id    = event.get("device_id",                "UNKNOWN")
    criticality  = event.get("patient_criticality_score", 0.0)
    timestamp    = event.get("timestamp",                 "")
    raw_payload  = event.get("raw_payload",               None)

    # ── LOCAL ALERT (simulates Amazon SNS local alert / paging the on-call doctor) ──
    # TODO AWS MIGRATION: replace print with boto3.client('sns').publish(
    #     TopicArn=..., Message=f"CRITICAL ALERT: {device_id} criticality={criticality}")
    import sys
    _out = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
    print(
        f"\n*** LOCAL ALERT TRIGGERED ***\n"
        f"   Device      : {device_id}\n"
        f"   Criticality : {criticality:.1f}/10\n"
        f"   Timestamp   : {timestamp}\n"
        f"   Action      : On-call physician paged immediately.\n",
        file=_out,
    )

    # ── Hot storage (simulates DynamoDB) ─────────────────────────────────────
    storage.init_db()
    storage.save_hot({
        "device_id":                 device_id,
        "timestamp":                 timestamp,
        "routing_decision":          event.get("routing_decision", "EDGE"),
        "reason":                    event.get("reason", "unknown"),
        "predicted_latency_ms":      event.get("predicted_latency_ms", 0.0),
        "patient_criticality_score": criticality,
    })

    # ── Cold storage (simulates S3) — only if raw payload is present ─────────
    if raw_payload:
        storage.save_cold(device_id, timestamp, raw_payload)

    # ── Structured log (simulates CloudWatch) ────────────────────────────────
    logger.log_event("EDGE_PROCESSED", {
        **event,
        "alerted": True,
    })

    return {
        "status":    "processed_at_edge",
        "device_id": device_id,
        "alerted":   True,
    }


if __name__ == "__main__":
    test_event = {
        "device_id":                 "ECG-101",
        "routing_decision":          "EDGE",
        "reason":                    "override_critical_patient",
        "patient_criticality_score": 9.5,
        "predicted_latency_ms":      210.5,
        "timestamp":                 "2026-09-22T10:15:32Z",
        "raw_payload": {
            "bandwidth_mbps":      15.2,
            "packet_loss_pct":     12.3,
            "jitter_ms":           67.0,
            "signal_strength_dbm": -74,
            "current_latency_ms":  280.0,
        },
    }
    result = handle_event(test_event)
    print("Edge node result:", result)
