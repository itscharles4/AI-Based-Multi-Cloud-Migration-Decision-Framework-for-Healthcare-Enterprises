"""
backend/routers/auth.py
=======================
Authentication endpoints:
  POST /auth/register  — create a new user (admin only after first admin)
  POST /auth/login     — returns access + refresh tokens
  POST /auth/refresh   — exchange refresh token for new access token
  POST /auth/logout    — blacklist the current token (Redis)
  GET  /auth/me        — return current user info
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database   import get_db
from backend.core.security   import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, UserRole
)
from backend.core.dependencies  import get_current_user
from backend.core.redis_client  import blacklist_token
from backend.core.config        import settings
from backend.models.user        import User, AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Schemas (inline Pydantic) ─────────────────────────────────────────────────
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username:  str       = Field(..., min_length=3, max_length=64)
    email:     EmailStr
    full_name: str       = Field(..., min_length=2, max_length=255)
    password:  str       = Field(..., min_length=8, max_length=128)
    role:      UserRole  = UserRole.DOCTOR
    department: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class UserResponse(BaseModel):
    id:         int
    username:   str
    email:      str
    full_name:  str
    role:       str
    department: str | None
    is_active:  bool


# ── Helper ────────────────────────────────────────────────────────────────────
async def _log_audit(db, user_id, event_type, resource, details, ip):
    entry = AuditLog(
        user_id=user_id, event_type=event_type,
        resource=resource, details=json.dumps(details),
        ip_address=ip,
    )
    db.add(entry)


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
             summary="Register a new user")
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new hospital staff account.
    First registered user automatically becomes admin.
    Subsequent users are created by admins only (enforced in /admin/users).
    """
    # Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Check email uniqueness
    existing_email = await db.execute(select(User).where(User.email == body.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # First user ever = auto admin
    user_count = await db.execute(select(User))
    is_first   = len(user_count.scalars().all()) == 0
    role       = UserRole.ADMIN if is_first else body.role

    user = User(
        username        = body.username,
        email           = body.email,
        full_name       = body.full_name,
        hashed_password = hash_password(body.password),
        role            = role,
        department      = body.department,
    )
    db.add(user)
    await db.flush()   # get user.id

    await _log_audit(db, user.id, "USER_CREATED",
                     f"user:{user.id}", {"username": body.username, "role": role.value},
                     request.client.host if request.client else None)

    logger.info("[auth] User registered: %s (role=%s)", body.username, role.value)

    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        full_name=user.full_name, role=user.role.value,
        department=user.department, is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse, summary="Login and get tokens")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with username + password.
    Returns JWT access token (60 min) and refresh token (7 days).
    """
    result = await db.execute(select(User).where(User.username == body.username))
    user   = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        await _log_audit(db, None, "LOGIN_FAILED",
                         f"user:{body.username}", {"reason": "bad_credentials"},
                         request.client.host if request.client else None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Update last_login
    user.last_login = datetime.now(timezone.utc)

    access_token  = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(user.id, user.username, user.role)

    await _log_audit(db, user.id, "LOGIN_SUCCESS",
                     f"user:{user.id}", {"username": user.username},
                     request.client.host if request.client else None)

    logger.info("[auth] Login: user=%s role=%s", user.username, user.role.value)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh(request: Request):
    """
    Exchange a valid refresh token for a new access token.
    Provide the refresh token in the Authorization: Bearer header.
    """
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token_str = auth[7:]
    token_data = decode_token(token_str, expected_type="refresh")

    new_access  = create_access_token(token_data.user_id, token_data.username, token_data.role)
    new_refresh = create_refresh_token(token_data.user_id, token_data.username, token_data.role)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", summary="Logout and blacklist token")
async def logout(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Blacklist the current access token so it cannot be reused.
    Client should discard both tokens after calling this.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        ttl   = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        await blacklist_token(token, ttl)

    await _log_audit(db, current_user.user_id, "LOGOUT",
                     f"user:{current_user.user_id}", {},
                     request.client.host if request.client else None)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse, summary="Get current user info")
async def me(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the profile of the currently authenticated user."""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        full_name=user.full_name, role=user.role.value,
        department=user.department, is_active=user.is_active,
    )
