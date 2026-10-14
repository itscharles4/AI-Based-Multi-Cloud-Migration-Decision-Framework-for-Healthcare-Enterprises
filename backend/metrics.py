"""Prometheus metrics — scraped from /metrics endpoint.

All metrics are module-level singletons (prometheus_client ensures single registration).
Import this module wherever you need to increment counters or observe histograms.

Usage:
    from backend.metrics import TELEMETRY, DECISIONS, ALERTS, PIPELINE_SECONDS
    TELEMETRY.labels("processed").inc()
    DECISIONS.labels("EDGE", "override_critical_patient").inc()
    PIPELINE_SECONDS.observe(elapsed)
"""
from prometheus_client import Counter, Histogram

# ── Telemetry ingestion ────────────────────────────────────────────────────────
TELEMETRY = Counter(
    "telemetry_total",
    "Telemetry messages received by the pipeline",
    ["status"],          # processed | duplicate | error
)

# ── Routing decisions ──────────────────────────────────────────────────────────
DECISIONS = Counter(
    "routing_decisions_total",
    "Routing decisions made by the AHP engine",
    ["decision", "reason"],  # decision: EDGE|CLOUD, reason: ahp|override|veto
)

# ── Alerts raised ─────────────────────────────────────────────────────────────
ALERTS = Counter(
    "alerts_total",
    "Clinical alerts raised (de-duplicated)",
    ["severity"],        # CRITICAL | WARNING
)

# ── Pipeline latency ──────────────────────────────────────────────────────────
PIPELINE_SECONDS = Histogram(
    "pipeline_seconds",
    "End-to-end pipeline time from ingest to DB commit",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)

# ── HTTP request latency ──────────────────────────────────────────────────────
HTTP_SECONDS = Histogram(
    "http_request_seconds",
    "HTTP request latency by route",
    ["method", "path", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# ── Dead-letter queue ──────────────────────────────────────────────────────────
DEAD_LETTERS = Counter(
    "dead_letters_total",
    "MQTT messages that could not be processed and were saved to dead_letters table",
)

# ── RIPE Atlas data fetches ───────────────────────────────────────────────────
RIPE_FETCHES = Counter(
    "ripe_atlas_fetches_total",
    "RIPE Atlas API data fetch operations",
    ["status"],          # success | error
)
