"""Tamper-evident audit trail: each row stores sha256(prev_hash + its own content).
Editing or deleting ANY historical row breaks every hash that follows it.
This gives us a HIPAA-aligned, append-only, cryptographically verifiable audit chain.

Usage:
    from backend.audit import write_audit, verify_chain
    write_audit(db, actor="charles", action="ingest", resource=f"device/{device_id}")
"""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models.user import AuditLog

GENESIS = "0" * 64  # Starting hash for the first entry


def _digest(prev: str, ts: str, actor: str, action: str, resource: str, detail: dict) -> str:
    """SHA-256 of a canonical JSON representation. Keys sorted so output is deterministic."""
    body = json.dumps(
        {"prev": prev, "ts": ts, "actor": actor, "action": action,
         "resource": resource, "detail": detail},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_audit(
    db: Session,
    actor: str,
    action: str,
    resource: str,
    detail: dict | None = None,
) -> AuditLog:
    """Append one audit entry. Caller is responsible for db.commit().

    FOR UPDATE serialises concurrent writers on PostgreSQL so the chain never forks.
    `detail` must contain JSON-native values only. NEVER include patient-identifying data (PHI).

    Args:
        actor:    Who performed the action (username or service name)
        action:   What was done  e.g. 'login', 'ingest', 'route_decision'
        resource: What was acted on  e.g. 'device/ECG-101'
        detail:   Optional dict of non-PHI metadata
    """
    detail = detail or {}
    last = db.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(1).with_for_update()
    ).scalar_one_or_none()
    prev = last.hash if last else GENESIS
    ts = datetime.now(timezone.utc).isoformat()
    row = AuditLog(
        ts=ts,
        actor=actor,
        action=action,
        resource=resource,
        detail=detail,
        prev_hash=prev,
        hash=_digest(prev, ts, actor, action, resource, detail),
    )
    db.add(row)
    db.flush()
    return row


def verify_chain(db: Session) -> tuple[bool, int | None]:
    """Walk the full audit log and verify every hash link.

    Returns:
        (True, None)      — chain is intact
        (False, broken_id) — row `broken_id` breaks the chain (tampering detected)
    """
    prev = GENESIS
    for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        expected = _digest(prev, row.ts, row.actor, row.action, row.resource, row.detail)
        if row.prev_hash != prev or row.hash != expected:
            return False, row.id
        prev = row.hash
    return True, None
