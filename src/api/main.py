"""
main.py  —  FastAPI Integration API
=====================================
This is the central orchestration layer that ties all three modules together.

Endpoints
---------
  POST /ingest  — Full pipeline: predict → decide → execute → log
  GET  /health  — Health check
  GET  /stats   — Routing distribution (EDGE vs CLOUD counts)

Full pipeline (POST /ingest)
-----------------------------
  1. Call predict_latency(window)     ← Charles's LSTM module
  2. Call route_decision(...)          ← Tanmay's AHP router
  3. Route to edge_node or cloud_node  ← Rani's execution layer
  4. log_event(PIPELINE_COMPLETE, ...) ← Rani's logger
  5. Return combined JSON response

AWS migration
-------------
  This FastAPI app is replaced by API Gateway + Lambda.
  The internal logic (steps 1-4) maps directly to Lambda functions
  as documented in the project guide Section 7.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn

from src.prediction.predict_service  import predict_latency
from src.decision.router             import route_decision
from src.execution.edge_node         import handle_event as edge_handle
from src.execution.cloud_node        import handle_event as cloud_handle
from src.execution.logger            import log_event
from src.execution.storage           import init_db, get_routing_distribution

# Ensure DB is ready
init_db()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Telemedicine Workload Offloader API",
    description=(
        "AI-Based Multi-Cloud Migration Decision Framework for Healthcare. "
        "Predicts network degradation, decides edge/cloud routing via AHP, "
        "and executes the routing with full audit logging."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # allow all origins for local dev/dashboard testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class TelemetryRecord(BaseModel):
    """Single IoMT telemetry reading."""
    timestamp:           str
    device_id:           str
    bandwidth_mbps:      float
    packet_loss_pct:     float
    jitter_ms:           float
    signal_strength_dbm: float
    current_latency_ms:  float


class IngestRequest(BaseModel):
    """Request body for POST /ingest."""
    window: List[TelemetryRecord] = Field(
        ...,
        description="Exactly 20 consecutive telemetry records (oldest → newest)",
        min_length=20,
        max_length=20,
    )
    patient_criticality_score: float = Field(
        ..., ge=0.0, le=10.0,
        description="Patient criticality 0-10 (10 = cardiac arrest)"
    )
    current_cloud_cost_index: float = Field(
        ..., ge=0.0, le=1.0,
        description="Normalised cloud compute cost index 0-1"
    )


class IngestResponse(BaseModel):
    """Full pipeline result returned to the caller."""
    device_id:                  str
    predicted_latency_ms:       float
    network_degradation_risk:   str
    routing_decision:           str
    reason:                     str
    cloud_score:                Optional[float]
    edge_score:                 Optional[float]
    execution_status:           str
    alerted:                    bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", summary="Health check")
def health():
    """Returns {"status": "ok"} when the service is running."""
    return {"status": "ok"}


@app.get("/stats", summary="Routing distribution statistics")
def stats():
    """
    Returns the count of EDGE vs CLOUD routing decisions across all events.
    Useful for quick testing without opening the dashboard.
    """
    return get_routing_distribution()


@app.post("/ingest", response_model=IngestResponse, summary="Full pipeline ingest")
def ingest(request: IngestRequest):
    """
    Run the complete prediction → decision → execution pipeline for one window.

    Steps:
      1. predict_latency(window) — LSTM model
      2. route_decision(...)     — AHP engine
      3. edge_node / cloud_node  — execution
      4. log_event(...)          — audit log
    """
    # Convert Pydantic models to plain dicts
    window_dicts = [r.model_dump() for r in request.window]

    # ── Step 1: Predict latency ──────────────────────────────────────────────
    try:
        prediction = predict_latency(window_dicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")

    device_id         = prediction["device_id"]
    predicted_latency = prediction["predicted_latency_ms"]

    # ── Step 2: Routing decision ─────────────────────────────────────────────
    try:
        decision = route_decision(
            device_id=device_id,
            patient_criticality_score=request.patient_criticality_score,
            predicted_latency_ms=predicted_latency,
            current_cloud_cost_index=request.current_cloud_cost_index,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {e}")

    # ── Step 3: Build event dict ─────────────────────────────────────────────
    last_reading = window_dicts[-1]
    event = {
        "device_id":                 device_id,
        "timestamp":                 last_reading["timestamp"],
        "routing_decision":          decision["routing_decision"],
        "reason":                    decision["reason"],
        "patient_criticality_score": request.patient_criticality_score,
        "predicted_latency_ms":      predicted_latency,
        "raw_payload":               last_reading,
    }

    # ── Step 4: Execute routing ──────────────────────────────────────────────
    if decision["routing_decision"] == "EDGE":
        exec_result = edge_handle(event)
    else:
        exec_result = cloud_handle(event)

    # ── Step 5: Audit log ────────────────────────────────────────────────────
    log_event("PIPELINE_COMPLETE", {
        **event,
        "predicted_latency_ms":     predicted_latency,
        "network_degradation_risk": prediction["network_degradation_risk"],
        "cloud_score":              decision.get("cloud_score"),
        "edge_score":               decision.get("edge_score"),
        "execution_status":         exec_result.get("status"),
    })

    # ── Step 6: Return combined response ────────────────────────────────────
    return IngestResponse(
        device_id=device_id,
        predicted_latency_ms=predicted_latency,
        network_degradation_risk=prediction["network_degradation_risk"],
        routing_decision=decision["routing_decision"],
        reason=decision["reason"],
        cloud_score=decision.get("cloud_score"),
        edge_score=decision.get("edge_score"),
        execution_status=exec_result.get("status", "unknown"),
        alerted=exec_result.get("alerted", False),
    )


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
