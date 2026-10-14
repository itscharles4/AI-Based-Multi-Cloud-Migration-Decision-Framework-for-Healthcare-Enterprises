"""
test_api.py
===========
Integration tests for the FastAPI /ingest, /health, and /stats endpoints.
Uses FastAPI's TestClient (via httpx) for in-process testing without
needing a running uvicorn server.

Tests cover:
  1. GET /health -> 200 {"status": "ok"}
  2. GET /stats  -> 200 returns a dict
  3. POST /ingest with valid payload -> 200 + correct response schema
  4. POST /ingest with too few records -> 422 validation error
  5. POST /ingest with criticality out of range -> 422 validation error
  6. POST /ingest with cost_index out of range -> 422 validation error
  7. POST /ingest verifies routing_decision is EDGE or CLOUD
  8. POST /ingest verifies alerted field is bool
  9. POST /ingest for critical patient returns alerted=True

Run with: pytest tests/test_api.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

WINDOW_SIZE = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_window(device_id="ECG-101", latency_ms=30.0, size=WINDOW_SIZE):
    """Build a synthetic telemetry window for API payloads."""
    return [
        {
            "timestamp":           f"2026-09-22T10:00:{i:02d}Z",
            "device_id":           device_id,
            "bandwidth_mbps":      60.0,
            "packet_loss_pct":     0.5,
            "jitter_ms":           6.0,
            "signal_strength_dbm": -65.0,
            "current_latency_ms":  latency_ms,
        }
        for i in range(size)
    ]


def _ingest_payload(device_id="ECG-101", latency_ms=30.0,
                    criticality=2.0, cost_index=0.3, size=WINDOW_SIZE):
    return {
        "window":                    _make_window(device_id=device_id, latency_ms=latency_ms, size=size),
        "patient_criticality_score": criticality,
        "current_cloud_cost_index":  cost_index,
    }


# ===========================================================================
# Health & Stats
# ===========================================================================
class TestHealthAndStats:

    def test_health_returns_200(self):
        """GET /health must return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_body(self):
        """GET /health must return {\"status\": \"ok\"}."""
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_stats_returns_200(self):
        """GET /stats must return HTTP 200."""
        response = client.get("/stats")
        assert response.status_code == 200

    def test_stats_returns_dict(self):
        """GET /stats must return a JSON dict (possibly empty)."""
        response = client.get("/stats")
        assert isinstance(response.json(), dict)


# ===========================================================================
# POST /ingest — valid payload
# ===========================================================================
class TestIngestValid:

    def test_ingest_returns_200(self):
        """POST /ingest with valid payload must return HTTP 200."""
        response = client.post("/ingest", json=_ingest_payload())
        assert response.status_code == 200, response.text

    def test_ingest_response_schema(self):
        """POST /ingest response must contain all required keys."""
        response = client.post("/ingest", json=_ingest_payload())
        body = response.json()
        required = {"device_id", "predicted_latency_ms", "network_degradation_risk",
                    "routing_decision", "reason", "execution_status", "alerted"}
        assert required.issubset(body.keys()), \
            f"Missing keys: {required - body.keys()}"

    def test_ingest_device_id_echoed(self):
        """POST /ingest must echo back the device_id from the window."""
        response = client.post("/ingest", json=_ingest_payload(device_id="WEARABLE-302"))
        assert response.json()["device_id"] == "WEARABLE-302"

    def test_ingest_routing_decision_valid(self):
        """routing_decision must be either EDGE or CLOUD."""
        response = client.post("/ingest", json=_ingest_payload())
        assert response.json()["routing_decision"] in {"EDGE", "CLOUD"}

    def test_ingest_alerted_is_bool(self):
        """alerted field must be a boolean."""
        response = client.post("/ingest", json=_ingest_payload())
        assert isinstance(response.json()["alerted"], bool)

    def test_ingest_risk_is_valid(self):
        """network_degradation_risk must be LOW, MEDIUM, or HIGH."""
        response = client.post("/ingest", json=_ingest_payload())
        assert response.json()["network_degradation_risk"] in {"LOW", "MEDIUM", "HIGH"}

    def test_ingest_reason_is_valid(self):
        """reason must be one of the three known values."""
        response = client.post("/ingest", json=_ingest_payload())
        valid_reasons = {"ahp_decision", "override_critical_patient", "network_degradation_veto"}
        assert response.json()["reason"] in valid_reasons

    def test_ingest_predicted_latency_is_non_negative(self):
        """predicted_latency_ms must be >= 0."""
        response = client.post("/ingest", json=_ingest_payload())
        assert response.json()["predicted_latency_ms"] >= 0.0


# ===========================================================================
# POST /ingest — clinical routing scenarios
# ===========================================================================
class TestIngestClinicalScenarios:

    def test_critical_patient_routes_to_edge(self):
        """Criticality=9.5 must route to EDGE and alerted=True."""
        payload = _ingest_payload(criticality=9.5, latency_ms=20.0, cost_index=0.1)
        response = client.post("/ingest", json=payload)
        body = response.json()
        assert body["routing_decision"] == "EDGE"
        assert body["alerted"] is True
        assert body["reason"] == "override_critical_patient"

    def test_routine_patient_healthy_network_cloud(self):
        """Criticality=1.0, good network -> should route to CLOUD."""
        payload = _ingest_payload(criticality=1.0, latency_ms=15.0, cost_index=0.1)
        response = client.post("/ingest", json=payload)
        body = response.json()
        assert body["routing_decision"] == "CLOUD"
        assert body["alerted"] is False

    def test_high_latency_routes_to_edge(self):
        """Very high latency (fallback gives ~440ms) triggers network veto -> EDGE."""
        # Fallback: 400 * 1.1 = 440ms >= 300ms -> network_degradation_veto
        payload = _ingest_payload(criticality=1.0, latency_ms=400.0, cost_index=0.2)
        response = client.post("/ingest", json=payload)
        body = response.json()
        assert body["routing_decision"] == "EDGE"


# ===========================================================================
# POST /ingest — validation error cases
# ===========================================================================
class TestIngestValidationErrors:

    def test_too_few_records_returns_422(self):
        """Window with < 20 records must return HTTP 422."""
        payload = _ingest_payload(size=10)
        response = client.post("/ingest", json=payload)
        assert response.status_code == 422

    def test_too_many_records_returns_422(self):
        """Window with > 20 records must return HTTP 422."""
        payload = _ingest_payload(size=25)
        response = client.post("/ingest", json=payload)
        assert response.status_code == 422

    def test_criticality_out_of_range_low_returns_422(self):
        """patient_criticality_score < 0 must return HTTP 422."""
        payload = _ingest_payload()
        payload["patient_criticality_score"] = -1.0
        response = client.post("/ingest", json=payload)
        assert response.status_code == 422

    def test_criticality_out_of_range_high_returns_422(self):
        """patient_criticality_score > 10 must return HTTP 422."""
        payload = _ingest_payload()
        payload["patient_criticality_score"] = 11.0
        response = client.post("/ingest", json=payload)
        assert response.status_code == 422

    def test_cost_index_out_of_range_low_returns_422(self):
        """current_cloud_cost_index < 0 must return HTTP 422."""
        payload = _ingest_payload()
        payload["current_cloud_cost_index"] = -0.5
        response = client.post("/ingest", json=payload)
        assert response.status_code == 422

    def test_cost_index_out_of_range_high_returns_422(self):
        """current_cloud_cost_index > 1 must return HTTP 422."""
        payload = _ingest_payload()
        payload["current_cloud_cost_index"] = 1.5
        response = client.post("/ingest", json=payload)
        assert response.status_code == 422

    def test_missing_window_returns_422(self):
        """Missing window field must return HTTP 422."""
        payload = {
            "patient_criticality_score": 2.0,
            "current_cloud_cost_index":  0.3,
        }
        response = client.post("/ingest", json=payload)
        assert response.status_code == 422

    def test_empty_body_returns_422(self):
        """Empty JSON body must return HTTP 422."""
        response = client.post("/ingest", json={})
        assert response.status_code == 422
