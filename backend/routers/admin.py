"""
backend/routers/admin.py
========================
Admin-only endpoints for user management:
  GET    /admin/users         — list all users
  POST   /admin/users         — create user (admin only)
  PATCH  /admin/users/{id}    — update role / active status
  DELETE /admin/users/{id}    — deactivate user
  GET    /admin/users/{id}/audit — audit trail for specific user
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.core.database    import get_db
from backend.core.security    import hash_password, require_role, UserRole
from backend.core.dependencies import get_current_user
from backend.models.user       import User, AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

_require_admin = require_role(UserRole.ADMIN)


# ── Schemas ───────────────────────────────────────────────────────────────────
class CreateUserRequest(BaseModel):
    username:   str      = Field(..., min_length=3, max_length=64)
    email:      EmailStr
    full_name:  str      = Field(..., min_length=2, max_length=255)
    password:   str      = Field(..., min_length=8, max_length=128)
    role:       UserRole = UserRole.DOCTOR
    department: Optional[str] = None


class UpdateUserRequest(BaseModel):
    role:       Optional[UserRole] = None
    is_active:  Optional[bool]     = None
    department: Optional[str]      = None


# ── Routes ────────────────────────────────────────────────────────────────────
@router.get("/users", summary="List all users (admin only)")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
):
    result = await db.execute(select(User).order_by(User.id))
    users  = result.scalars().all()
    return [
        {
            "id":         u.id,
            "username":   u.username,
            "email":      u.email,
            "full_name":  u.full_name,
            "role":       u.role.value,
            "department": u.department,
            "is_active":  u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
        }
        for u in users
    ]


@router.post("/users", status_code=status.HTTP_201_CREATED, summary="Create user (admin only)")
async def create_user(
    body: CreateUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(_require_admin),
):
    # Check uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    existing_email = await db.execute(select(User).where(User.email == body.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username        = body.username,
        email           = body.email,
        full_name       = body.full_name,
        hashed_password = hash_password(body.password),
        role            = body.role,
        department      = body.department,
    )
    db.add(user)
    await db.flush()

    db.add(AuditLog(
        user_id    = admin.user_id,
        event_type = "USER_CREATED",
        resource   = f"user:{user.id}",
        details    = json.dumps({"created_username": body.username, "role": body.role.value}),
        ip_address = request.client.host if request.client else None,
    ))

    logger.info("[admin] User created: %s by admin %s", body.username, admin.username)
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.patch("/users/{user_id}", summary="Update user role or status (admin only)")
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(_require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes = {}
    if body.role is not None:
        changes["role"] = body.role.value
        user.role = body.role
    if body.is_active is not None:
        changes["is_active"] = body.is_active
        user.is_active = body.is_active
    if body.department is not None:
        changes["department"] = body.department
        user.department = body.department

    db.add(AuditLog(
        user_id    = admin.user_id,
        event_type = "USER_UPDATED",
        resource   = f"user:{user_id}",
        details    = json.dumps(changes),
        ip_address = request.client.host if request.client else None,
    ))

    return {"message": "User updated", "changes": changes}


@router.delete("/users/{user_id}", summary="Deactivate user (admin only)")
async def deactivate_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(_require_admin),
):
    if user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.add(AuditLog(
        user_id    = admin.user_id,
        event_type = "USER_DEACTIVATED",
        resource   = f"user:{user_id}",
        details    = json.dumps({"deactivated_username": user.username}),
        ip_address = request.client.host if request.client else None,
    ))

    logger.info("[admin] User deactivated: %s by admin %s", user.username, admin.username)
    return {"message": f"User '{user.username}' deactivated"}


@router.get("/users/{user_id}/audit", summary="Audit trail for a specific user")
async def user_audit(
    user_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(desc(AuditLog.timestamp))
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id":         r.id,
            "event_type": r.event_type,
            "resource":   r.resource,
            "ip_address": r.ip_address,
            "timestamp":  r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]
