"""
backend/models/telemetry.py
============================
SQLAlchemy ORM model for raw IoMT telemetry readings.

This table is converted to a TimescaleDB hypertable (partitioned by timestamp)
via the Alembic migration — giving us:
  - Fast range queries (last 1 hour, last 24 hours)
  - Automatic chunk compression for older data
  - Continuous aggregates for dashboard metrics
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Index
)
from backend.core.database import Base


class TelemetryReading(Base):
    """
    One row = one sensor reading from one IoMT device.
    Ingested via POST /ingest (sliding windows of 20) or MQTT.

    TimescaleDB hypertable:
      - Partitioned by `timestamp` (7-day chunks)
      - Indexed on (device_id, timestamp DESC) for fast per-device queries
    """
    __tablename__ = "telemetry_readings"

    # TimescaleDB requires (timestamp, ...) as composite primary key
    # when using hypertables.  We use an integer surrogate + unique constraint.
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    timestamp           = Column(DateTime(timezone=True), nullable=False, index=True)
    device_id           = Column(String(32),  nullable=False, index=True)

    # Network telemetry features
    bandwidth_mbps      = Column(Float, nullable=False)
    packet_loss_pct     = Column(Float, nullable=False)
    jitter_ms           = Column(Float, nullable=False)
    signal_strength_dbm = Column(Float, nullable=False)
    current_latency_ms  = Column(Float, nullable=False)

    # Metadata
    ingested_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Composite index for per-device time-range queries
    __table_args__ = (
        Index("ix_telemetry_device_time", "device_id", "timestamp"),
    )

    def __repr__(self):
        return (
            f"<TelemetryReading device={self.device_id!r} "
            f"ts={self.timestamp} lat={self.current_latency_ms}ms>"
        )

    def to_dict(self) -> dict:
        return {
            "id":                   self.id,
            "timestamp":            self.timestamp.isoformat(),
            "device_id":            self.device_id,
            "bandwidth_mbps":       self.bandwidth_mbps,
            "packet_loss_pct":      self.packet_loss_pct,
            "jitter_ms":            self.jitter_ms,
            "signal_strength_dbm":  self.signal_strength_dbm,
            "current_latency_ms":   self.current_latency_ms,
        }
