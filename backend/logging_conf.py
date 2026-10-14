"""Structured JSON logging via structlog.

Rule: NEVER log vitals values, patient names, or anything patient-identifying.
      Telemetry is device-level and pseudonymous. Logs are JSON lines, one per event.

Usage:
    import structlog
    log = structlog.get_logger()
    log.info("telemetry_processed", device_id="ECG-101", decision="EDGE")

On AWS: replace PrintLoggerFactory with watchtower.CloudWatchLogHandler.
"""
import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for JSON-line output. Call once at app startup."""
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=lvl)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,          # injects request_id per request
            structlog.processors.add_log_level,               # adds "level" field
            structlog.processors.TimeStamper(fmt="iso", utc=True),  # adds "timestamp"
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),               # final JSON output
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Convenience wrapper — same as structlog.get_logger() but importable from one place."""
    return structlog.get_logger(name)
