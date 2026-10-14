"""
backend/core/dependencies.py
============================
FastAPI dependency injection helpers.
Injected into routes via Depends().
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import decode_token, TokenData
from backend.core.redis_client import check_rate_limit

# Re-export get_db for convenience
__all__ = ["get_db", "get_current_user", "require_rate_limit"]

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    """
    Dependency: validate JWT bearer token and return token data.
    Raises 401 if token is missing, invalid, or expired.

    Usage:
        @router.get("/protected")
        async def endpoint(user: TokenData = Depends(get_current_user)):
            return {"user": user.username}
    """
    token = credentials.credentials
    return decode_token(token, expected_type="access")


async def require_rate_limit(
    user: TokenData = Depends(get_current_user),
) -> TokenData:
    """
    Dependency: enforce per-user rate limit (100 req/min by default).
    Raises 429 if the user exceeds their rate limit.
    Chain after get_current_user.

    Usage:
        @router.post("/ingest")
        async def endpoint(user: TokenData = Depends(require_rate_limit)):
            ...
    """
    allowed = await check_rate_limit(user.user_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 100 requests per minute.",
            headers={"Retry-After": "60"},
        )
    return user
