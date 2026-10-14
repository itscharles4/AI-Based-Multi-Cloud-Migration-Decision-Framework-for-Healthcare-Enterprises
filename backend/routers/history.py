"""
backend/routers/history.py
===========================
Query endpoints for the dashboard and auditors:
  GET /stats        — EDGE vs CLOUD distribution
  GET /history      — paginated routing decisions
  GET /devices      — list of active devices
  GET /history/{id} — single decision detail
  GET /audit        — HIPAA audit log (admin/auditor only)
  GET /export       — export as CSV (auditor+)
"""

import csv
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from backend.core.database    import get_db
from backend.core.dependencies import get_current_user
from backend.core.security    import require_role, UserRole
from backend.core.redis_client import cache_get, cache_set
from backend.models.routing   import RoutingDecision
from backend.models.user      import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(tags=["History & Stats"])


# ── GET /stats ─────────────────────────────────────────────────────────────────
@router.get("/stats", summary="Routing distribution statistics")
async def get_stats(
    hours: int = Query(24, ge=1, le=720, description="Look-back window in hours"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Returns EDGE vs CLOUD counts, total events, and risk distribution
    for the specified look-back window (default: last 24 hours).
    Results are cached in Redis for 60 seconds.
    """
    cache_key = f"routing_distribution:{hours}h"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Routing distribution
    dist_result = await db.execute(
        select(RoutingDecision.routing_decision, func.count().label("count"))
        .where(RoutingDecision.stored_at >= since)
        .group_by(RoutingDecision.routing_decision)
    )
    distribution = {row.routing_decision: row.count for row in dist_result}

    # Risk distribution
    risk_result = await db.execute(
        select(RoutingDecision.network_degradation_risk, func.count().label("count"))
        .where(RoutingDecision.stored_at >= since)
        .group_by(RoutingDecision.network_degradation_risk)
    )
    risk_dist = {row.network_degradation_risk: row.count for row in risk_result}

    # Reason distribution
    reason_result = await db.execute(
        select(RoutingDecision.reason, func.count().label("count"))
        .where(RoutingDecision.stored_at >= since)
        .group_by(RoutingDecision.reason)
    )
    reason_dist = {row.reason: row.count for row in reason_result}

    # Average latency
    avg_result = await db.execute(
        select(func.avg(RoutingDecision.predicted_latency_ms))
        .where(RoutingDecision.stored_at >= since)
    )
    avg_latency = float(avg_result.scalar() or 0.0)

    total = sum(distribution.values())
    response = {
        "window_hours":       hours,
        "total_events":       total,
        "distribution":       distribution,
        "edge_pct":           round(distribution.get("EDGE",  0) / max(total, 1) * 100, 1),
        "cloud_pct":          round(distribution.get("CLOUD", 0) / max(total, 1) * 100, 1),
        "risk_distribution":  risk_dist,
        "reason_distribution": reason_dist,
        "avg_predicted_latency_ms": round(avg_latency, 2),
        "emergency_overrides": reason_dist.get("override_critical_patient", 0),
        "network_vetoes":      reason_dist.get("network_degradation_veto", 0),
    }

    await cache_set(cache_key, response, ttl=60)
    return response


# ── GET /history ───────────────────────────────────────────────────────────────
@router.get("/history", summary="Paginated routing decision history")
async def get_history(
    page:      int = Query(1,   ge=1),
    page_size: int = Query(50,  ge=1, le=500),
    device_id: Optional[str]  = Query(None),
    decision:  Optional[str]  = Query(None, pattern="^(EDGE|CLOUD)$"),
    hours:     int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Paginated, filterable history of routing decisions.
    Filters: device_id, decision (EDGE|CLOUD), hours window.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = select(RoutingDecision).where(RoutingDecision.stored_at >= since)

    if device_id:
        query = query.where(RoutingDecision.device_id == device_id)
    if decision:
        query = query.where(RoutingDecision.routing_decision == decision)

    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    # Paginate
    query = query.order_by(desc(RoutingDecision.stored_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows   = result.scalars().all()

    return {
        "page":        page,
        "page_size":   page_size,
        "total":       total,
        "total_pages": (total + page_size - 1) // page_size,
        "items":       [r.to_dict() for r in rows],
    }


# ── GET /devices ───────────────────────────────────────────────────────────────
@router.get("/devices", summary="List active IoMT devices")
async def get_devices(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return list of distinct device IDs seen in the last 24 hours."""
    since  = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(RoutingDecision.device_id)
        .where(RoutingDecision.stored_at >= since)
        .distinct()
    )
    return {"devices": [row.device_id for row in result]}


# ── GET /history/{id} ──────────────────────────────────────────────────────────
@router.get("/history/{decision_id}", summary="Single routing decision detail")
async def get_decision(
    decision_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(RoutingDecision).where(RoutingDecision.id == decision_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row.to_dict()


# ── GET /audit ─────────────────────────────────────────────────────────────────
@router.get("/audit", summary="HIPAA audit log (admin/auditor only)")
async def get_audit_log(
    page:       int = Query(1,  ge=1),
    page_size:  int = Query(50, ge=1, le=200),
    event_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.AUDITOR)),
):
    """Returns paginated HIPAA audit trail. Requires auditor role or higher."""
    query = select(AuditLog)
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    query  = query.order_by(desc(AuditLog.timestamp))
    query  = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows   = result.scalars().all()
    return {
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id":         r.id,
                "user_id":    r.user_id,
                "event_type": r.event_type,
                "resource":   r.resource,
                "ip_address": r.ip_address,
                "timestamp":  r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ],
    }


# ── GET /export ────────────────────────────────────────────────────────────────
@router.get("/export", summary="Export routing history as CSV")
async def export_csv(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.AUDITOR)),
):
    """
    Download all routing decisions from the last N hours as a CSV file.
    Requires auditor role or higher.
    """
    since  = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(RoutingDecision)
        .where(RoutingDecision.stored_at >= since)
        .order_by(RoutingDecision.stored_at)
    )
    rows = result.scalars().all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id","timestamp","device_id","predicted_latency_ms","network_degradation_risk",
        "patient_criticality_score","current_cloud_cost_index","routing_decision",
        "reason","edge_score","cloud_score","execution_status","alerted","stored_at",
    ])
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_dict())

    output.seek(0)
    filename = f"routing_history_{hours}h_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
