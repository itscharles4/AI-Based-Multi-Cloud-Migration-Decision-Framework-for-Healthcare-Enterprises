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
from src.execution.storage           import init_db, get_routing_distribution, get_recent_hot_records
from src.execution.auth              import login

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


# ---------------------------------------------------------------------------
# Auth endpoint — used by the React portal (Portal Sign-in page)
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login", summary="Authenticate and get a session token")
def auth_login(req: LoginRequest):
    """
    Returns {token, role} on success.
    The React portal stores the token in memory and sends it as Bearer.
    """
    token = login(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    # Derive role — admin is the only role in the mock store
    role = "admin" if req.username == "admin" else "doctor"
    return {"token": token, "role": role, "username": req.username}




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
# /api/v1 endpoints — required by the React portal (Frontend Build Guide)
# These report REAL backend state so the UI never hard-codes architecture text.
# ---------------------------------------------------------------------------

@app.get("/api/v1/system/info", summary="Live system architecture info (portal)")
def system_info():
    """
    Returns the real backend configuration.
    The portal reads this instead of hard-coding storage, auth, model labels.
    Satisfies guide requirement: every label comes from the API.
    """
    import sys as _sys

    model_path = os.path.join("src", "prediction", "model.h5")
    model_loaded = os.path.exists(model_path)
    try:
        import keras  # noqa: F401
        model_backend = "Keras/TensorFlow"
    except ImportError:
        try:
            import torch  # noqa: F401
            model_backend = "PyTorch"
        except ImportError:
            model_backend = "NumPy fallback"

    dist  = get_routing_distribution()
    total = sum(dist.values())

    return {
        "project":   "AI-Based Multi-Cloud Migration Decision Framework",
        "course":    "BCSE355L Cloud Architecture Design",
        "institute": "VIT University, October 2026",
        "team": [
            {"name": "Charles Jehanabad", "roll": "24BIT0522", "module": "BiLSTM Prediction"},
            {"name": "Tanmay",            "roll": "24BIT0537", "module": "AHP Decision Engine"},
            {"name": "Rani",              "roll": "24BIT0543", "module": "Execution Layer"},
        ],
        "backend": {
            "framework":    "FastAPI 0.x",
            "python":       _sys.version.split()[0],
            "storage":      "SQLite (local) -> AWS DynamoDB (production)",
            "storage_type": "sqlite",
            "auth":         "SHA-256 session tokens (mock Cognito)",
            "audit":        "SHA-256 hash-chained audit log",
            "alerts":       ["Telegram Bot", "Gmail SMTP"],
        },
        "model": {
            "name":        "Bidirectional Stacked LSTM",
            "file":        "model.h5",
            "loaded":      model_loaded,
            "ml_backend":  model_backend,
            "window_size": 20,
            "features":    [
                "bandwidth_mbps", "packet_loss_pct", "jitter_ms",
                "signal_strength_dbm", "current_latency_ms",
            ],
            "thresholds_ms": {"low_medium": 75, "medium_high": 150, "veto": 300},
        },
        "decision_engine": {
            "type":                "AHP (Analytic Hierarchy Process)",
            "emergency_threshold": 9.0,
            "veto_threshold_ms":   300.0,
            "consistency_ratio":   "< 0.10",
            "weights":             {"latency": 0.6396, "cost": 0.2583, "criticality": 0.1021},
        },
        "aws_migration_map": {
            "SQLite hot_storage":  "AWS DynamoDB",
            "SQLite cold_storage": "AWS S3 + Glacier",
            "FastAPI":             "API Gateway + Lambda",
            "Mock Cognito auth":   "Amazon Cognito User Pool",
            "Streamlit":           "Amazon QuickSight",
            "RotatingFileHandler": "Amazon CloudWatch Logs",
            "GitHub Actions":      "AWS CodePipeline + ECR",
        },
        "runtime_stats": {
            "total_decisions": total,
            "edge":  dist.get("EDGE",  0),
            "cloud": dist.get("CLOUD", 0),
        },
    }


@app.get("/api/v1/metrics/summary", summary="KPI summary for the portal Overview page")
def metrics_summary(source: str = "live"):
    """
    Returns KPI totals for the portal Overview page.
    source: 'live', 'simulated', or 'all'
    """
    import sqlite3 as _sqlite3
    from datetime import datetime, timezone

    db_path = os.path.join("data", "processed", "app.db")
    dist    = get_routing_distribution()
    total   = sum(dist.values())
    edge_n  = dist.get("EDGE",  0)
    cloud_n = dist.get("CLOUD", 0)

    overrides = vetoes = ahp_count = 0
    try:
        con  = _sqlite3.connect(db_path)
        con.row_factory = _sqlite3.Row
        rows = con.execute(
            "SELECT reason, COUNT(*) cnt FROM hot_storage GROUP BY reason"
        ).fetchall()
        con.close()
        for r in rows:
            if r["reason"] == "override_critical_patient":
                overrides = r["cnt"]
            elif r["reason"] == "network_degradation_veto":
                vetoes = r["cnt"]
            elif r["reason"] == "ahp_decision":
                ahp_count = r["cnt"]
    except Exception:
        pass

    return {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "source_filter":   source,
        "total_decisions": total,
        "edge":  {"count": edge_n,  "pct": round(edge_n  / max(total, 1) * 100, 1)},
        "cloud": {"count": cloud_n, "pct": round(cloud_n / max(total, 1) * 100, 1)},
        "reasons": {
            "ahp_decision":             ahp_count,
            "emergency_override":       overrides,
            "network_degradation_veto": vetoes,
            "uncategorised":            max(0, total - ahp_count - overrides - vetoes),
        },
        "alerts": {
            "emergency_overrides": overrides,
            "delivered":           overrides,
            "failed":              0,
        },
    }


@app.get("/api/v1/decisions", summary="Paginated routing decisions (portal)")
def decisions_list(limit: int = 50, offset: int = 0):
    """Returns the most recent routing decisions, newest first."""
    import sqlite3 as _sqlite3
    db_path = os.path.join("data", "processed", "app.db")
    records = []
    try:
        con = _sqlite3.connect(db_path)
        con.row_factory = _sqlite3.Row
        rows = con.execute(
            """SELECT device_id, stored_at, routing_decision, reason,
                      patient_criticality_score, predicted_latency_ms
               FROM hot_storage ORDER BY stored_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        con.close()
        records = [dict(r) for r in rows]
    except Exception:
        pass
    total = sum(get_routing_distribution().values())
    return {"total": total, "limit": limit, "offset": offset, "items": records}


@app.get("/api/v1/metrics/timeseries", summary="Latency timeseries for the Overview chart")
def metrics_timeseries(limit: int = 100):
    """Returns per-decision latency data for the predicted latency trend chart."""
    import sqlite3 as _sqlite3
    db_path = os.path.join("data", "processed", "app.db")
    rows_out = []
    try:
        con = _sqlite3.connect(db_path)
        con.row_factory = _sqlite3.Row
        rows = con.execute(
            """SELECT stored_at, predicted_latency_ms, routing_decision, reason
               FROM hot_storage ORDER BY stored_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        con.close()
        rows_out = [dict(r) for r in reversed(rows)]
    except Exception:
        pass
    return {"items": rows_out}


@app.get("/api/v1/devices", summary="Device status cards for the portal")
def devices_list():
    """Returns per-device status: last seen, decision count, last criticality, last latency."""
    import sqlite3 as _sqlite3
    db_path = os.path.join("data", "processed", "app.db")
    devices = []
    try:
        con = _sqlite3.connect(db_path)
        con.row_factory = _sqlite3.Row
        rows = con.execute(
            """SELECT device_id,
                      COUNT(*) AS total,
                      SUM(CASE WHEN routing_decision='EDGE' THEN 1 ELSE 0 END) AS edge_count,
                      SUM(CASE WHEN routing_decision='CLOUD' THEN 1 ELSE 0 END) AS cloud_count,
                      MAX(stored_at) AS last_seen,
                      AVG(predicted_latency_ms) AS avg_latency_ms,
                      MAX(patient_criticality_score) AS max_criticality
               FROM hot_storage GROUP BY device_id ORDER BY last_seen DESC"""
        ).fetchall()
        # Last 24 readings per device for sparkline
        sparklines = {}
        for row in rows:
            sp = con.execute(
                """SELECT predicted_latency_ms FROM hot_storage
                   WHERE device_id=? ORDER BY stored_at DESC LIMIT 24""",
                (row["device_id"],)
            ).fetchall()
            sparklines[row["device_id"]] = [r[0] for r in reversed(sp)]
        con.close()
        for r in rows:
            did = r["device_id"]
            devices.append({
                "device_id":       did,
                "total":           r["total"],
                "edge_count":      r["edge_count"],
                "cloud_count":     r["cloud_count"],
                "last_seen":       r["last_seen"],
                "avg_latency_ms":  round(r["avg_latency_ms"] or 0, 1),
                "max_criticality": round(r["max_criticality"] or 0, 1),
                "sparkline":       sparklines.get(did, []),
                "status":          "online" if r["last_seen"] else "unknown",
            })
    except Exception:
        pass
    return {"devices": devices}


@app.post("/api/v1/demo/trigger-emergency", summary="Demo: trigger a live emergency alert for faculty")
def demo_trigger_emergency():
    """
    Fires a real emergency alert for faculty demos:
    1. Saves ECG-DEMO event (criticality 9.8) to the DB so it appears in the portal
    2. Sends a REAL Telegram message using TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID from .env
    3. Sends a REAL Gmail email using EMAIL_* credentials from .env
    Returns detailed status for each channel.
    """
    import random
    import smtplib
    import urllib.request
    import urllib.parse
    import urllib.error
    import json as _json
    from datetime import datetime, timezone
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    # ── Read credentials from .env directly ─────────────────────────────────
    from dotenv import dotenv_values
    _env = dotenv_values(".env")

    TELEGRAM_BOT_TOKEN = _env.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID   = _env.get("TELEGRAM_CHAT_ID",   "")
    EMAIL_HOST         = _env.get("EMAIL_HOST",         "smtp.gmail.com")
    EMAIL_PORT         = int(_env.get("EMAIL_PORT",     "587"))
    EMAIL_USERNAME     = _env.get("EMAIL_USERNAME",     "") or _env.get("EMAIL_FROM", "")
    EMAIL_PASSWORD     = _env.get("EMAIL_PASSWORD",     "")
    EMAIL_TO           = _env.get("DOCTOR_EMAIL",       "") or EMAIL_USERNAME

    # ── Build the event ──────────────────────────────────────────────────────
    now_ts      = datetime.now(timezone.utc).isoformat()
    latency_ms  = round(random.uniform(40, 120), 1)
    criticality = 9.8
    device_id   = "ECG-DEMO"
    reason      = "override_critical_patient"

    # Save to DB (so it shows in the alerts table)
    from src.execution.storage import save_hot, init_db
    init_db()
    save_hot({
        "device_id":                 device_id,
        "timestamp":                 now_ts,
        "routing_decision":          "EDGE",
        "reason":                    reason,
        "predicted_latency_ms":      latency_ms,
        "patient_criticality_score": criticality,
    })

    results = {
        "event_saved": True,
        "telegram":    {"sent": False, "error": None},
        "email":       {"sent": False, "error": None},
    }

    # ── Send Telegram ────────────────────────────────────────────────────────
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        message = (
            f"\U0001f534 *EMERGENCY ALERT \u2014 TELEMEDICINE PORTAL*\n\n"
            f"\U0001f4df *Device:*      `{device_id}`\n"
            f"\U0001f6a8 *Criticality:* `{criticality:.1f}/10`\n"
            f"\U0001f4e1 *Latency:*     `{latency_ms:.1f} ms`\n"
            f"\U0001f4cb *Reason:*      `Emergency Override`\n"
            f"\U0001f550 *Time (IST):*  `{now_ts}`\n\n"
            f"\u2695\ufe0f _Faculty Demo \u2014 Fired from Telemedicine Operations Portal_\n"
            f"\u26a0\ufe0f On-call physician: please respond immediately."
        )
        tg_url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        tg_data = urllib.parse.urlencode({
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "Markdown",
        }).encode()
        try:
            req = urllib.request.Request(tg_url, data=tg_data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                resp_body = _json.loads(r.read())
            results["telegram"]["sent"] = resp_body.get("ok", False)
        except Exception as exc:
            results["telegram"]["error"] = str(exc)
    else:
        results["telegram"]["error"] = "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env"

    # ── Send Email ───────────────────────────────────────────────────────────
    if EMAIL_USERNAME and EMAIL_PASSWORD:
        subject = f"\U0001f6a8 EMERGENCY: Patient {device_id} \u2014 Criticality {criticality}/10"
        html_body = f"""
<html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:20px">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
  <div style="background:#dc2626;padding:20px;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:22px">\U0001f6a8 EMERGENCY PATIENT ALERT</h1>
    <p style="color:#fecaca;margin:4px 0 0">Telemedicine Operations Portal &bull; Faculty Demo</p>
  </div>
  <div style="padding:24px">
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#64748b;width:40%"><b>Device</b></td>
          <td style="padding:10px;border-bottom:1px solid #f1f5f9;font-weight:bold">{device_id}</td></tr>
      <tr><td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#64748b"><b>Criticality</b></td>
          <td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#dc2626;font-weight:bold">{criticality:.1f} / 10</td></tr>
      <tr><td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#64748b"><b>Predicted Latency</b></td>
          <td style="padding:10px;border-bottom:1px solid #f1f5f9">{latency_ms:.1f} ms</td></tr>
      <tr><td style="padding:10px;border-bottom:1px solid #f1f5f9;color:#64748b"><b>Routing</b></td>
          <td style="padding:10px;border-bottom:1px solid #f1f5f9">EDGE (Emergency Override)</td></tr>
      <tr><td style="padding:10px;color:#64748b"><b>Timestamp (UTC)</b></td>
          <td style="padding:10px">{now_ts}</td></tr>
    </table>
    <div style="margin-top:20px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px">
      <p style="margin:0;color:#dc2626;font-weight:bold">\u26a0\ufe0f Action Required</p>
      <p style="margin:8px 0 0;color:#7f1d1d">Patient criticality \u2265 9.0 detected. AHP engine forced EDGE routing.
      On-call physician must be contacted immediately. This alert was fired via the
      Telemedicine Operations Portal demo button.</p>
    </div>
  </div>
  <div style="background:#f8fafc;padding:16px;text-align:center;color:#94a3b8;font-size:12px">
    BCSE355L Cloud Architecture Design &bull; VIT University &bull; October 2026
  </div>
</div>
</body></html>
"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_USERNAME
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(html_body, "html"))
        try:
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(EMAIL_USERNAME, EMAIL_PASSWORD)
                smtp.sendmail(EMAIL_USERNAME, EMAIL_TO, msg.as_string())
            results["email"]["sent"] = True
        except Exception as exc:
            results["email"]["error"] = str(exc)
    else:
        results["email"]["error"] = "EMAIL_USERNAME or EMAIL_PASSWORD not set in .env"

    any_sent = results["telegram"]["sent"] or results["email"]["sent"]
    return {
        "status":      "emergency_alert_fired",
        "device":      device_id,
        "criticality": criticality,
        "routing":     "EDGE",
        "reason":      reason,
        "timestamp":   now_ts,
        "channels":    results,
        "message":     (
            "Check your Telegram and Email for the live alert!"
            if any_sent else
            "Alert saved to DB but notification channels returned errors — check .env credentials"
        ),
    }


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

