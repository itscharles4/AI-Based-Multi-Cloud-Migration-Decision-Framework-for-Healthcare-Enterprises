"""
backend/routers/health.py
==========================
Health check and Prometheus metrics endpoints:
  GET /health    — liveness probe (no auth)
  GET /ready     — readiness probe (checks DB + Redis)
  GET /metrics   — Prometheus text format metrics
"""

import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from sqlalchemy import text

from backend.core.database    import engine
from backend.core.redis_client import get_redis
from backend.core.config      import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

# App start time for uptime metric
_START_TIME = time.time()


@router.get("/health", summary="Liveness probe — always returns 200 if app is running")
async def health():
    """Used by Docker / Railway health checks. No auth required."""
    return {
        "status":      "ok",
        "version":     settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready", summary="Readiness probe — checks DB and Redis connectivity")
async def readiness():
    """
    Used by Kubernetes/Railway before routing traffic to this pod.
    Returns 503 if PostgreSQL or Redis is unreachable.
    """
    checks = {}
    status_code = 200

    # Check PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        status_code = 503

    # Check Redis
    try:
        r = get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        status_code = 503

    return Response(
        content=f'{{"status": "{"ok" if status_code == 200 else "degraded"}", "checks": {checks}}}',
        status_code=status_code,
        media_type="application/json",
    )


@router.get("/metrics", summary="Prometheus metrics (text format)")
async def prometheus_metrics():
    """
    Expose Prometheus-compatible metrics.
    Scraped by Prometheus every 15 seconds (configured in monitoring/prometheus.yml).

    Metrics exported:
      - telemedicine_uptime_seconds
      - telemedicine_requests_total (by endpoint)
      - telemedicine_routing_decisions_total (by decision type)
      - telemedicine_alerts_sent_total
    """
    from backend.core.redis_client import get_redis
    r = get_redis()

    uptime = time.time() - _START_TIME

    # Read counters from Redis (incremented by pipeline)
    async def _get_counter(key: str) -> int:
        val = await r.get(f"metrics:{key}")
        return int(val) if val else 0

    edge_count   = await _get_counter("routing:EDGE")
    cloud_count  = await _get_counter("routing:CLOUD")
    alerts_total = await _get_counter("alerts:sent")
    ingest_total = await _get_counter("requests:ingest")

    lines = [
        "# HELP telemedicine_uptime_seconds Time since API started",
        "# TYPE telemedicine_uptime_seconds gauge",
        f"telemedicine_uptime_seconds {uptime:.2f}",
        "",
        "# HELP telemedicine_routing_decisions_total Total routing decisions by type",
        "# TYPE telemedicine_routing_decisions_total counter",
        f'telemedicine_routing_decisions_total{{decision="EDGE"}} {edge_count}',
        f'telemedicine_routing_decisions_total{{decision="CLOUD"}} {cloud_count}',
        "",
        "# HELP telemedicine_alerts_total Total emergency alerts sent",
        "# TYPE telemedicine_alerts_total counter",
        f"telemedicine_alerts_total {alerts_total}",
        "",
        "# HELP telemedicine_ingest_requests_total Total /ingest requests",
        "# TYPE telemedicine_ingest_requests_total counter",
        f"telemedicine_ingest_requests_total {ingest_total}",
        "",
    ]

    return Response(
        content="\n".join(lines),
        media_type="text/plain; version=0.0.4",
    )
