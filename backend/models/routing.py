"""
backend/models/routing.py
==========================
SQLAlchemy ORM models for routing decisions and cold storage.

Tables:
  - routing_decisions  : every EDGE/CLOUD decision (TimescaleDB hypertable)
  - cold_storage       : raw payload archive (S3 equivalent)
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    Text, Enum as SAEnum, Index
)

from backend.core.database import Base


class RoutingDecision(Base):
    """
    One row = one complete routing decision event.
    Stores the full pipeline result for auditing and dashboard queries.
    Converted to a TimescaleDB hypertable via Alembic migration.
    """
    __tablename__ = "routing_decisions"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    timestamp                = Column(DateTime(timezone=True), nullable=False, index=True)
    device_id                = Column(String(32),  nullable=False, index=True)

    # Prediction output
    predicted_latency_ms     = Column(Float, nullable=False)
    network_degradation_risk = Column(String(8), nullable=False)   # LOW | MEDIUM | HIGH

    # Patient context
    patient_criticality_score = Column(Float, nullable=False)
    current_cloud_cost_index  = Column(Float, nullable=False)

    # Decision output
    routing_decision = Column(String(8), nullable=False)    # EDGE | CLOUD
    reason           = Column(String(64), nullable=False)
    # override_critical_patient | network_degradation_veto | ahp_decision
    edge_score       = Column(Float, nullable=True)
    cloud_score      = Column(Float, nullable=True)

    # Execution output
    execution_status = Column(String(32), nullable=False)   # processed_at_edge | processed_in_cloud
    alerted          = Column(Integer, nullable=False, default=0)  # 0=False, 1=True

    # Request metadata
    user_id          = Column(Integer, nullable=True)       # who submitted the /ingest request
    request_source   = Column(String(16), nullable=False, default="http")  # http | mqtt
    stored_at        = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_routing_device_time", "device_id", "timestamp"),
        Index("ix_routing_decision_type", "routing_decision"),
    )

    def __repr__(self):
        return (
            f"<RoutingDecision device={self.device_id!r} "
            f"decision={self.routing_decision!r} "
            f"lat={self.predicted_latency_ms}ms>"
        )

    def to_dict(self) -> dict:
        return {
            "id":                        self.id,
            "timestamp":                 self.timestamp.isoformat() if self.timestamp else None,
            "device_id":                 self.device_id,
            "predicted_latency_ms":      self.predicted_latency_ms,
            "network_degradation_risk":  self.network_degradation_risk,
            "patient_criticality_score": self.patient_criticality_score,
            "current_cloud_cost_index":  self.current_cloud_cost_index,
            "routing_decision":          self.routing_decision,
            "reason":                    self.reason,
            "edge_score":                self.edge_score,
            "cloud_score":               self.cloud_score,
            "execution_status":          self.execution_status,
            "alerted":                   bool(self.alerted),
            "user_id":                   self.user_id,
            "request_source":            self.request_source,
            "stored_at":                 self.stored_at.isoformat() if self.stored_at else None,
        }


class ColdStorage(Base):
    """
    Raw telemetry payload archive (equivalent to S3 objects).
    One row per /ingest request — stores the full raw window JSON.
    """
    __tablename__ = "cold_storage"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    device_id   = Column(String(32),  nullable=False, index=True)
    timestamp   = Column(DateTime(timezone=True), nullable=False)
    raw_payload = Column(Text, nullable=False)   # JSON string of full window
    stored_at   = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<ColdStorage device={self.device_id!r} ts={self.timestamp}>"
