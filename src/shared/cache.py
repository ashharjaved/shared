from __future__ import annotations

import os
import time
from typing import Any, Optional, Protocol, Tuple, runtime_checkable
from src.config import get_settings

# Use redis.asyncio instead of aioredis
try:
    from redis import asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore


@runtime_checkable
class CacheBackend(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def setex(self, key: str, ttl_sec: int, value: Any) -> None: ...
    async def delete(self, key: str) -> None: ...


class _InMemoryTTLCache:
    """
    Process-local TTL cache (MVP). Not multi-process safe.
    """
    def __init__(self):
        self._store: dict[Tuple[str, str], Tuple[Any, float]] = {}

    async def get(self, key: str) -> Any | None:
        now = time.time()
        entry = self._store.get(("k", key))
        if not entry:
            return None
        value, exp = entry
        if now >= exp:
            self._store.pop(("k", key), None)
            return None
        return value

    async def setex(self, key: str, ttl_sec: int, value: Any) -> None:
        self._store[("k", key)] = (value, time.time() + ttl_sec)

    async def delete(self, key: str) -> None:
        self._store.pop(("k", key), None)


class _RedisCache:
    """
    Thin wrapper to satisfy the CacheBackend Protocol and keep strong typing.
    """
    def __init__(self, url: str):
        # aioredis.from_url returns a Redis[Any]; we don't rely on generics here
        self._client = aioredis.from_url(url, decode_responses=True)  # type: ignore[union-attr]

    async def get(self, key: str) -> Any | None:
        return await self._client.get(key)

    async def setex(self, key: str, ttl_sec: int, value: Any) -> None:
        # redis-py setex signature: setex(name, time, value)
        await self._client.setex(key, ttl_sec, value)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)


# Global redis client instance
_redis: Optional[aioredis.Redis] = None  # type: ignore

async def get_redis() -> aioredis.Redis:  # type: ignore
    """
    Returns a singleton aioredis client.
    Uses REDIS_URL env var or defaults to redis://localhost:6379/0.
    """
    global _redis
    if _redis is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        # decode_responses=True so we always get str from redis
        _redis = aioredis.from_url(  # type: ignore
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis  # type: ignore

async def close_redis() -> None:
    """Close redis connection if initialized."""
    global _redis
    if _redis is not None:
        await _redis.close()  # type: ignore
        _redis = None


class Cache:
    """
    Typed facade that always exposes a non-optional backend.
    Fixes Pylance `reportOptionalMemberAccess` by avoiding Optional fields.
    """
    def __init__(self):
        settings = get_settings()

        backend: CacheBackend
        if aioredis is not None and settings.REDIS_URL:
            backend = _RedisCache(str(settings.REDIS_URL))
        else:
            backend = _InMemoryTTLCache()

        self._backend: CacheBackend = backend

    async def get(self, key: str) -> Any | None:
        return await self._backend.get(key)

    async def setex(self, key: str, ttl_sec: int, value: Any) -> None:
        await self._backend.setex(key, ttl_sec, value)

    async def delete(self, key: str) -> None:
        await self._backend.delete(key)


# Singleton accessor (lazy)
_cache_singleton: Cache | None = None

def get_cache() -> Cache:
    global _cache_singleton
    if _cache_singleton is None:
        _cache_singleton = Cache()
    return _cache_singleton