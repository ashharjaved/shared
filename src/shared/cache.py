"""
Async Redis connector (append-only friendly).

Policy alignment:
- REDIS_USAGE.md: Redis is an optimization; DB remains source of truth.
- TTLs: sessions=30m, rate-limit=1m, cache=5m default (configurable via env).
- Keys: tenant:{id}:session:{user}, ratelimit:{tenant}:{endpoint}, cache:{tenant}:{object}
"""

from __future__ import annotations

import os
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

from redis.asyncio import Redis, ConnectionPool

# redis>=4.2 uses redis.asyncio for asyncio support
try:
    from redis.asyncio import Redis as AsyncRedis, ConnectionPool
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "redis-py with asyncio is required. Install: `pip install redis>=4.5`"
    ) from exc

# -----------------------------
# Environment / Defaults
# -----------------------------
# Add connection validation
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
if not REDIS_URL.startswith(("redis://", "rediss://")):
    raise ValueError("Invalid REDIS_URL format")

REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "2.0"))
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))

# Policy-default TTLs (can be overridden per use site)
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(30 * 60)))  # 30m
RATE_LIMIT_TTL_SECONDS = int(os.getenv("RATE_LIMIT_TTL_SECONDS", "60"))    # 1m
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", str(5 * 60)))       # 5m

# -----------------------------
# Lazy singleton pool + client
# -----------------------------
_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None
_lock = asyncio.Lock()


async def _ensure_client() -> AsyncRedis:
    """
    Ensure a global AsyncRedis client exists (lazy, thread-safe).
    """
    global _pool, _client
    if _client is not None:
        return _client

    async with _lock:
        if _client is not None:
            return _client

        _pool = ConnectionPool.from_url(
            REDIS_URL,
            max_connections=REDIS_MAX_CONNECTIONS,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            decode_responses=True,  # store text (JSON, counters) as str
        )
        _client = AsyncRedis(connection_pool=_pool)
        # quick health check (non-fatal if Redis is down; callers can handle)
        try:
            await _client.ping()
        except Exception:
            # We intentionally swallow here to avoid boot failure; later calls may still work
            pass

        return _client

async def get_redis() -> Redis:
    """Lazily create a global async Redis client (thread-safe)."""
    global _pool, _client
    if _client is not None:
        return _client
    async with _lock:
        if _client is not None:
            return _client
        _pool = ConnectionPool.from_url(
            REDIS_URL,
            max_connections=REDIS_MAX_CONNECTIONS,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
        _client = Redis(connection_pool=_pool)
        return _client


async def close_redis() -> None:
    """
    Gracefully close the global client/pool (useful for test teardown).
    """
    global _client, _pool
    if _client is not None:
        try:
            await _client.close()
        except Exception:
            pass
    if _pool is not None:
        try:
            await _pool.disconnect()
        except Exception:
            pass
    _client = None
    _pool = None

@asynccontextmanager
async def pipeline(transaction: bool = False):
    """
    Async pipeline context manager. Caller awaits `pipe.execute()` manually.
    """
    r = await get_redis()
    pipe = r.pipeline(transaction=transaction)
    try:
        yield pipe
    finally:
        try:
            await pipe.reset()
        except Exception:
            pass
# -----------------------------
# Small convenience helpers
# -----------------------------
async def cache_set(key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
    r = await get_redis()
    await r.set(key, value, ex=ttl_seconds or CACHE_TTL_SECONDS)


async def cache_get(key: str) -> Optional[str]:
    r = await get_redis()
    return await r.get(key)


@asynccontextmanager
async def rate_limit_pipeline():
    """
    Context manager that yields a pipeline for atomic rate-limit operations.

    Example:
        async with rate_limit_pipeline() as pipe:
            pipe.incr(key, 1)
            pipe.expire(key, RATE_LIMIT_TTL_SECONDS)
            count, _ = await pipe.execute()
    """
    r = await get_redis()
    pipe = r.pipeline(transaction=False)
    try:
        yield pipe
    finally:
        # redis-py pipeline doesn't need explicit close in asyncio, but be explicit for clarity
        try:
            await pipe.reset()
        except Exception:
            pass
