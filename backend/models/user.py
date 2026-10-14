"""
backend/models/user.py
======================
SQLAlchemy ORM models for users, roles, audit logging, device registry, alerts,
and dead-letter queue.

Tables:
  - users           : hospital staff accounts (admin, doctor, auditor)
  - devices         : registered IoMT device registry
  - audit_log       : tamper-evident hash-chained audit trail (HIPAA-aligned)
  - alerts          : persisted clinical alerts with deduplication support
  - dead_letters    : MQTT messages that failed processing (nothing silently dropped)
"""

import uuid as _uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, Enum as SAEnum, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.core.database import Base
from backend.core.security import UserRole

# Portable JSON type: JSONB on PostgreSQL, plain JSON on SQLite (for tests)
_JsonType = JSON()


class User(Base):
    """
    Hospital staff account.
    Passwords are bcrypt-hashed — never stored in plaintext.
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(64), unique=True, nullable=False, index=True)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    full_name     = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role          = Column(SAEnum(UserRole), nullable=False, default=UserRole.DOCTOR)
    is_active     = Column(Boolean, default=True, nullable=False)
    department    = Column(String(128), nullable=True)
    created_at    = Column(DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login    = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class Device(Base):
    """
    IoMT device registry. Auto-registers on first telemetry reading.
    Allows admins to deactivate misbehaving devices without deleting history.
    AWS equivalent: AWS IoT Core Thing registry.
    """
    __tablename__ = "devices"

    id           = Column(String(64), primary_key=True)   # e.g. "ECG-101"
    kind         = Column(String(32), default="unknown", nullable=False)
    location     = Column(String(64), nullable=True)
    is_active    = Column(Boolean, default=True, nullable=False)
    registered_at = Column(DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<Device id={self.id!r} kind={self.kind!r} active={self.is_active}>"


class AuditLog(Base):
    """
    Tamper-evident, hash-chained audit trail. (HIPAA-aligned)

    Each row stores:
      prev_hash  — SHA-256 of the previous row's content
      hash       — SHA-256 of (prev_hash + this row's content)

    Editing or deleting ANY historical row breaks every hash that follows it,
    making tampering immediately detectable via backend.audit.verify_chain().

    Records are INSERT-ONLY. Never update or delete rows here.
    Never store PHI (patient identifiers, names, vitals values) in `detail`.
    """
    __tablename__ = "audit_log"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    ts        = Column(String(40), nullable=False)          # ISO-8601, UTC
    actor     = Column(String(64), nullable=False)          # username or service name
    action    = Column(String(64), nullable=False)          # e.g. 'login', 'ingest'
    resource  = Column(String(128), nullable=False)         # e.g. 'device/ECG-101'
    detail    = Column(_JsonType, default=dict, nullable=False)  # non-PHI metadata
    prev_hash = Column(String(64), nullable=False)
    hash      = Column(String(64), unique=True, nullable=False)

    def __repr__(self):
        return f"<AuditLog id={self.id} action={self.action!r} actor={self.actor!r}>"


class Alert(Base):
    """
    Persisted clinical alert. Created by the pipeline when routing_decision == EDGE
    and risk == HIGH, or when emergency override fires.

    The pipeline de-duplicates: only one alert per (device_id, severity) is created
    within a 60-second window to prevent alert storms.

    acknowledged_by / acknowledged_at support doctor acknowledgement workflow.
    AWS equivalent: Amazon SNS notification + DynamoDB acknowledgement table.
    """
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("device_id", "ts", "severity", name="uq_alert_device_ts_sev"),
    )

    id              = Column(String(36), primary_key=True,
                             default=lambda: str(_uuid.uuid4()))
    device_id       = Column(String(64), ForeignKey("devices.id"), nullable=False, index=True)
    ts              = Column(DateTime(timezone=True), nullable=False, index=True)
    severity        = Column(String(16), nullable=False)    # CRITICAL | WARNING
    message         = Column(Text, nullable=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True),
                             default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<Alert id={self.id} device={self.device_id!r} severity={self.severity}>"


class DeadLetter(Base):
    """
    MQTT messages the ingestor could not process are saved here.
    Nothing is silently dropped — every failure is recorded for later inspection.
    AWS equivalent: SQS Dead-Letter Queue.
    """
    __tablename__ = "dead_letters"

    id          = Column(String(36), primary_key=True,
                         default=lambda: str(_uuid.uuid4()))
    received_at = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(timezone.utc), nullable=False)
    topic       = Column(String(200), nullable=False)   # MQTT topic
    payload     = Column(Text, nullable=False)           # raw JSON payload
    error       = Column(Text, nullable=False)           # exception message

    def __repr__(self):
        return f"<DeadLetter id={self.id} topic={self.topic!r}>"
