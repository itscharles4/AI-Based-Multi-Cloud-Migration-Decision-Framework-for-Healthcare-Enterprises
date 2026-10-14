"""
backend/core/security.py
========================
JWT authentication + bcrypt password hashing + RBAC.

Roles (in order of privilege):
  - auditor  : read-only access to history and stats
  - doctor   : can view events, get alerts, query by device
  - admin    : full access including user management

JWT token types:
  - access_token  : short-lived (60 min default), used in Authorization header
  - refresh_token : long-lived (7 days), used to renew access tokens
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from enum import Enum

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from pydantic import BaseModel

from backend.core.config import settings


# ── Roles ─────────────────────────────────────────────────────────────────────
class UserRole(str, Enum):
    ADMIN   = "admin"
    DOCTOR  = "doctor"
    AUDITOR = "auditor"


ROLE_HIERARCHY = {
    UserRole.AUDITOR: 0,
    UserRole.DOCTOR:  1,
    UserRole.ADMIN:   2,
}


# ── Password hashing ──────────────────────────────────────────────────────────
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ── Token models ──────────────────────────────────────────────────────────────
class TokenData(BaseModel):
    user_id: int
    username: str
    role: UserRole
    token_type: str = "access"   # "access" | "refresh"


# ── JWT creation ──────────────────────────────────────────────────────────────
def create_access_token(user_id: int, username: str, role: UserRole) -> str:
    """
    Create a short-lived JWT access token.
    Expires in ACCESS_TOKEN_EXPIRE_MINUTES (default 60).
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub":        str(user_id),
        "username":   username,
        "role":       role.value,
        "token_type": "access",
        "exp":        expire,
        "iat":        datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int, username: str, role: UserRole) -> str:
    """
    Create a long-lived JWT refresh token.
    Expires in REFRESH_TOKEN_EXPIRE_DAYS (default 7).
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub":        str(user_id),
        "username":   username,
        "role":       role.value,
        "token_type": "refresh",
        "exp":        expire,
        "iat":        datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── JWT decoding ──────────────────────────────────────────────────────────────
def decode_token(token: str, expected_type: str = "access") -> TokenData:
    """
    Decode and validate a JWT token.
    Raises HTTPException 401 on any error.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: Optional[str] = payload.get("sub")
        username: Optional[str]    = payload.get("username")
        role_str: Optional[str]    = payload.get("role")
        token_type: Optional[str]  = payload.get("token_type")

        if not user_id_str or not username or not role_str:
            raise credentials_exception

        if token_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type: expected '{expected_type}', got '{token_type}'",
            )

        return TokenData(
            user_id=int(user_id_str),
            username=username,
            role=UserRole(role_str),
            token_type=token_type,
        )

    except JWTError:
        raise credentials_exception


# ── RBAC helper ───────────────────────────────────────────────────────────────
def require_role(minimum_role: UserRole):
    """
    Returns a FastAPI dependency that enforces a minimum role level.

    Usage:
        @router.delete("/users/{id}")
        async def delete_user(
            token_data: TokenData = Depends(require_role(UserRole.ADMIN))
        ):
            ...
    """
    from fastapi import Depends
    from backend.core.dependencies import get_current_user

    async def role_checker(token_data: TokenData = Depends(get_current_user)) -> TokenData:
        if ROLE_HIERARCHY[token_data.role] < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{minimum_role.value}' role or higher. You have '{token_data.role.value}'.",
            )
        return token_data

    return role_checker
