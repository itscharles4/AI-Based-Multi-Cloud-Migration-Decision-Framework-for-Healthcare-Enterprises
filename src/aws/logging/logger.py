# TODO AWS MIGRATION: replace file handler with watchtower or boto3 CloudWatch Logs client
"""
logger.py
=========
Structured logging module standing in for Amazon CloudWatch Logs.

Every routing decision, edge/cloud processing event, and pipeline completion
is logged as a JSON-formatted line to both the console and a rotating file
at logs/system.log.

Log format (JSON lines)
-----------------------
  {
    "timestamp": "2026-09-22T10:15:32.123456",
    "level": "INFO",
    "event_type": "ROUTING_DECISION",
    "details": { ...event-specific fields... }
  }

On AWS migration
----------------
  Replace the RotatingFileHandler with:
    import watchtower, boto3
    handler = watchtower.CloudWatchLogHandler(log_group="TelemedicineSystem")
  The log_event() function signature remains unchanged.
"""

import os
import json
import logging
import logging.handlers
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
_LOG_DIR  = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "system.log")
os.makedirs(_LOG_DIR, exist_ok=True)


class _JSONFormatter(logging.Formatter):
    """Custom formatter that serialises log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "level":      record.levelname,
            "event_type": getattr(record, "event_type", "GENERIC"),
            "details":    getattr(record, "details",    {}),
            "message":    record.getMessage(),
        }
        return json.dumps(log_obj)


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("telemedicine_system")
    if logger.handlers:
        return logger   # already configured (avoid duplicate handlers in Streamlit)

    logger.setLevel(logging.DEBUG)

    formatter = _JSONFormatter()

    # --- Console handler ---
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # --- Rotating file handler (max 5 MB, keep 3 backups) ---
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


_logger = _build_logger()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def log_event(event_type: str, details: dict) -> None:
    """
    Log a structured event at INFO level.

    Parameters
    ----------
    event_type : str   e.g. "ROUTING_DECISION", "EDGE_PROCESSED", "PIPELINE_COMPLETE"
    details    : dict  Arbitrary key-value pairs to include in the JSON log entry.
    """
    _logger.info(
        f"[{event_type}]",
        extra={"event_type": event_type, "details": details},
    )


def log_warning(event_type: str, details: dict) -> None:
    """Log at WARNING level."""
    _logger.warning(
        f"[{event_type}]",
        extra={"event_type": event_type, "details": details},
    )


def log_error(event_type: str, details: dict) -> None:
    """Log at ERROR level."""
    _logger.error(
        f"[{event_type}]",
        extra={"event_type": event_type, "details": details},
    )


if __name__ == "__main__":
    log_event("ROUTING_DECISION", {
        "device_id":        "ECG-101",
        "routing_decision": "EDGE",
        "reason":           "override_critical_patient",
    })
    log_event("EDGE_PROCESSED", {
        "device_id": "ECG-101",
        "status":    "processed_at_edge",
        "alerted":   True,
    })
    print(f"Logs written to {_LOG_FILE}")
