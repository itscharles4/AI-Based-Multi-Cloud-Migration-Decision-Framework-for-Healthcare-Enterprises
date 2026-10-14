"""
backend/routers/ingest.py
==========================
POST /ingest  — Production pipeline endpoint.

Changes vs prototype:
  - JWT authentication required
  - Rate limiting (100 req/min per user)
  - Idempotency key support (X-Idempotency-Key header)
  - Async PostgreSQL writes (via pipeline service)
  - Real Telegram + Email alerts
  - Prometheus metrics incremented
  - HIPAA audit log entry on every call
"""

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database    import get_db
from backend.core.dependencies import require_rate_limit
from backend.core.redis_client import check_idempotency, cache_delete
from backend.services.pipeline import run_pipeline
from backend.models.user       import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Pipeline"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class TelemetryRecord(BaseModel):
    timestamp:           str
    device_id:           str
    bandwidth_mbps:      float
    packet_loss_pct:     float
    jitter_ms:           float
    signal_strength_dbm: float
    current_latency_ms:  float


class IngestRequest(BaseModel):
    window: List[TelemetryRecord] = Field(
        ...,
        description="Exactly 20 consecutive telemetry records (oldest to newest)",
        min_length=20,
        max_length=20,
    )
    patient_criticality_score: float = Field(..., ge=0.0, le=10.0)
    current_cloud_cost_index:  float = Field(..., ge=0.0, le=1.0)


class IngestResponse(BaseModel):
    device_id:                  str
    predicted_latency_ms:       float
    network_degradation_risk:   str
    routing_decision:           str
    reason:                     str
    cloud_score:                Optional[float]
    edge_score:                 Optional[float]
    execution_status:           str
    alerted:                    bool
    forecast_horizon_seconds:   int = 30


# ── Route ─────────────────────────────────────────────────────────────────────
@router.post("/ingest", response_model=IngestResponse, summary="Full pipeline ingest")
async def ingest(
    body: IngestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_rate_limit),
    x_idempotency_key: Optional[str] = Header(default=None),
):
    """
    Run the complete prediction → decision → execution pipeline.

    **Authentication:** Bearer token required.
    **Rate limit:** 100 requests per minute per user.
    **Idempotency:** Optional `X-Idempotency-Key` header — same key returns cached response.

    Steps:
    1. Check idempotency key (return cached response if seen before)
    2. Run LSTM prediction
    3. Run AHP routing decision
    4. Persist to PostgreSQL
    5. Fire Telegram + Email alert if emergency
    6. Return result
    """

    # ── Idempotency check ─────────────────────────────────────────────────────
    if x_idempotency_key:
        cached = await check_idempotency(x_idempotency_key, {})
        if cached and cached.get("_populated"):
            logger.info("[ingest] Returning cached response for idempotency key %s", x_idempotency_key)
            return IngestResponse(**{k: v for k, v in cached.items() if k != "_populated"})

    # ── Convert Pydantic to dicts ─────────────────────────────────────────────
    window_dicts = [r.model_dump() for r in body.window]

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        result = await run_pipeline(
            window                    = window_dicts,
            patient_criticality_score = body.patient_criticality_score,
            current_cloud_cost_index  = body.current_cloud_cost_index,
            db                        = db,
            user_id                   = current_user.user_id,
            request_source            = "http",
        )
    except Exception as exc:
        logger.error("[ingest] Pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    # ── HIPAA audit log ───────────────────────────────────────────────────────
    db.add(AuditLog(
        user_id    = current_user.user_id,
        event_type = "INGEST",
        resource   = f"device:{result['device_id']}",
        details    = json.dumps({
            "routing_decision": result["routing_decision"],
            "reason":           result["reason"],
            "latency_ms":       result["predicted_latency_ms"],
        }),
        ip_address = request.client.host if request.client else None,
    ))

    # ── Invalidate stats cache ────────────────────────────────────────────────
    await cache_delete("routing_distribution")

    # ── Store idempotency result ──────────────────────────────────────────────
    if x_idempotency_key:
        cached_result = {**result, "_populated": True}
        await check_idempotency(x_idempotency_key, cached_result)

    return IngestResponse(**result)
