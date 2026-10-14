"""
backend/models/user.py
======================
SQLAlchemy ORM models for users, roles, and audit logging.

Tables:
  - users       : hospital staff accounts (admin, doctor, auditor)
  - audit_log   : HIPAA-required immutable record of every action
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import relationship

from backend.core.database import Base
from backend.core.security import UserRole


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

    # Relationships
    audit_entries = relationship("AuditLog", back_populates="user",
                                 cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class AuditLog(Base):
    """
    HIPAA-required audit trail.
    Every login, logout, data access, and routing event is recorded here.
    Records are INSERT-only — never updated or deleted.
    """
    __tablename__ = "audit_log"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type  = Column(String(64), nullable=False, index=True)
    # e.g.: LOGIN, LOGOUT, INGEST, ROUTING_DECISION, DATA_EXPORT, USER_CREATED
    resource    = Column(String(255), nullable=True)
    # e.g.: "device:ECG-101", "user:42"
    details     = Column(Text, nullable=True)
    # JSON string with extra context
    ip_address  = Column(String(45), nullable=True)
    # IPv4 or IPv6
    timestamp   = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(timezone.utc),
                         nullable=False, index=True)

    user = relationship("User", back_populates="audit_entries")

    def __repr__(self):
        return f"<AuditLog id={self.id} event={self.event_type!r} user_id={self.user_id}>"
