"""
backend/core/redis_client.py
============================
Redis connection pool for:
  - Rate limiting (per-user request counters)
  - Session / token blacklist (logout invalidation)
  - Response caching (stats, distribution)
  - Idempotency keys (prevent duplicate /ingest calls)
"""

import json
import logging
from typing import Optional, Any

import redis.asyncio as aioredis
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Module-level pool — initialised on app startup
_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """Initialise the Redis connection pool. Called at app startup."""
    global _redis
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Ping to fail fast if Redis is unreachable
    await _redis.ping()
    logger.info("[redis] Connected to %s", settings.REDIS_URL)


async def close_redis() -> None:
    """Close the Redis connection pool. Called at app shutdown."""
    global _redis
    if _redis:
        await _redis.aclose()
        logger.info("[redis] Connection closed")


def get_redis() -> aioredis.Redis:
    """Return the active Redis client (dependency-injection friendly)."""
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() at startup.")
    return _redis


# ── Rate Limiting ─────────────────────────────────────────────────────────────
async def check_rate_limit(user_id: int) -> bool:
    """
    Sliding window rate limiter.
    Returns True if the request is allowed, False if rate limit exceeded.
    Allows RATE_LIMIT_PER_MINUTE requests per user per minute.
    """
    r = get_redis()
    key = f"rate_limit:{user_id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 60)   # set TTL only on first increment
    return count <= settings.RATE_LIMIT_PER_MINUTE


# ── Token Blacklist (logout) ──────────────────────────────────────────────────
async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """Add a JWT token ID to the blacklist (logout / forced expiry)."""
    r = get_redis()
    await r.setex(f"blacklist:{jti}", ttl_seconds, "1")


async def is_token_blacklisted(jti: str) -> bool:
    """Check if a token has been blacklisted."""
    r = get_redis()
    return await r.exists(f"blacklist:{jti}") > 0


# ── Idempotency Keys ──────────────────────────────────────────────────────────
async def check_idempotency(key: str, response: dict, ttl: int = 86400) -> Optional[dict]:
    """
    Check if a request with this idempotency key was already processed.
    If yes, returns the cached response.
    If no, stores the response and returns None.

    Usage: POST /ingest with X-Idempotency-Key header.
    """
    r = get_redis()
    redis_key = f"idempotency:{key}"
    existing = await r.get(redis_key)
    if existing:
        return json.loads(existing)
    await r.setex(redis_key, ttl, json.dumps(response))
    return None


# ── Cache ─────────────────────────────────────────────────────────────────────
async def cache_get(key: str) -> Optional[Any]:
    """Get a cached value (deserialised from JSON)."""
    r = get_redis()
    val = await r.get(f"cache:{key}")
    return json.loads(val) if val else None


async def cache_set(key: str, value: Any, ttl: int = None) -> None:
    """Set a cached value (serialised to JSON)."""
    r = get_redis()
    ttl = ttl or settings.REDIS_CACHE_TTL
    await r.setex(f"cache:{key}", ttl, json.dumps(value))


async def cache_delete(key: str) -> None:
    """Invalidate a cache key."""
    r = get_redis()
    await r.delete(f"cache:{key}")
