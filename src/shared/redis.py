# src/shared/redis_client.py
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional, TypeVar, Generic, Callable
from uuid import UUID

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from shared.utils.strings import slugify
from src.shared.config import settings
from src.shared.errors import AppError

T = TypeVar("T")

_KEY_SAFE = re.compile(r"[^a-z0-9:_\-]")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lock(self, key: str, ttl_seconds: int = 10, owner_token: str | None = None):
    token = owner_token or str(id(asyncio.current_task()))
    acquired = await self.acquire_lock(key, token, ttl_seconds)
    try:
        yield acquired
    finally:
        if acquired:
            await self.release_lock(key, token)


def _default_json_serializer(obj: Any) -> Any:
    # Minimal helper: handle UUIDs transparently
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

class RedisClient:
    """Async Redis client with standardized key patterns, health checks, and utilities."""

    def __init__(self, url: Optional[str] = None, namespace: Optional[str] = None):
        self._url = url or str(settings.redis_url)
        # isolate by environment/app (e.g., "prod:raydian")
        env = getattr(settings, "env", "prod")
        app_ns = getattr(settings, "app_namespace", "raydian")
        self._ns = (namespace or f"{env}:{app_ns}").strip(":")
        self.redis: Optional[Redis] = None
        self._lock = asyncio.Lock()

        # Preload small Lua scripts
        self._rate_limit_sha: Optional[str] = None
        self._unlock_sha: Optional[str] = None

    # ---------- connection management ----------

    async def connect(self) -> None:
        """Create client and verify connection."""
        if self.redis is not None:
            return
        try:
            # NOTE: from_url is sync; do NOT await it
            self.redis = redis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,            # return str instead of bytes
                health_check_interval=30,         # ping occasionally
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
                retry_on_timeout=True,
                max_connections=100,
            )
            # Verify we can reach Redis
            await self.redis.ping()

            # Load scripts
            self._rate_limit_sha = await self.redis.script_load(self._RATE_LIMIT_LUA)
            self._unlock_sha = await self.redis.script_load(self._UNLOCK_LUA)
        except Exception as e:
            self.redis = None
            raise AppError(f"Redis connection failed: {e}") from e

    async def ensure_connected(self) -> None:
        """Make sure a healthy connection exists; reconnect if needed."""
        if self.redis is None:
            await self.connect()
            return
        try:
            await self.redis.ping()
        except Exception:
            # reconnect under lock to avoid stampede
            async with self._lock:
                try:
                    if self.redis is not None:
                        await self.redis.close()
                        await self.redis.connection_pool.disconnect()  # purge sockets
                except Exception:
                    pass
                self.redis = None
                await self.connect()


    # ---------- low-level helpers ----------

    def _k(self, *parts: Any) -> str:
        # Build a namespaced key: "<ns>:<p1>:<p2>:..."
        norm = [str(p) for p in parts if p is not None and str(p) != ""]
        return ":".join([self._ns, *norm])

    async def _guard(self, fn: Callable[[], Any]) -> Any:
        if self.redis is None:
            await self.connect()
        await self.ensure_connected()
        if self.redis is None:
            raise AppError("Redis client not connected")
        try:
            return await fn()
        except RedisError as e:
            raise AppError(f"Redis error: {e}") from e

    # ---------- string & json ----------

    async def get(self, key: str) -> Optional[str]:
        return await self._guard(lambda: self.redis.get(key))  # type: ignore[union-attr]

    async def set(self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False) -> bool:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=_default_json_serializer)
        return await self._guard(lambda: self.redis.set(key, value, ex=ex, nx=nx))  # type: ignore[union-attr]

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        payload = json.dumps(value, default=_default_json_serializer)
        return await self._guard(lambda: self.redis.set(key, payload, ex=ex))  # type: ignore[union-attr]

    async def delete(self, key: str) -> bool:
        return await self._guard(lambda: self.redis.delete(key)) > 0  # type: ignore[union-attr]

    async def exists(self, key: str) -> bool:
        return await self._guard(lambda: self.redis.exists(key)) > 0  # type: ignore[union-attr]

    async def incr(self, key: str) -> int:
        return await self._guard(lambda: self.redis.incr(key))  # type: ignore[union-attr]

    async def expire(self, key: str, ttl: int) -> bool:
        return await self._guard(lambda: self.redis.expire(key, ttl))  # type: ignore[union-attr]

    async def ttl(self, key: str) -> int:
        return await self._guard(lambda: self.redis.ttl(key))  # type: ignore[union-attr]

    async def mget(self, keys: list[str]) -> list[Optional[str]]:
        return await self._guard(lambda: self.redis.mget(keys))  # type: ignore[union-attr]

    async def mset(self, mapping: dict[str, Any]) -> bool:
        # auto serialize dict/list values
        payload = {
            k: (json.dumps(v, default=_default_json_serializer) if isinstance(v, (dict, list)) else v)
            for k, v in mapping.items()
        }
        return await self._guard(lambda: self.redis.mset(payload))  # type: ignore[union-attr]

    # ---------- rate limiting (atomic) ----------

    _RATE_LIMIT_LUA = """
    -- KEY[1] = counter key
    -- ARGV[1] = window ttl seconds
    -- ARGV[2] = max count
    local c = redis.call('INCR', KEYS[1])
    if c == 1 then
      redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
    end
    if c > tonumber(ARGV[2]) then
      return {0, c}
    else
      return {1, c}
    end
    """

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Increment and check remaining quota atomically.
        Returns (allowed, current_count).
        """
        async def _run():
            # Use EVALSHA when available, fallback to EVAL
            try:
                return await self.redis.evalsha(self._rate_limit_sha, 1, key, window_seconds, limit)  # type: ignore[arg-type,union-attr]
            except RedisError:
                return await self.redis.eval(self._RATE_LIMIT_LUA, 1, key, window_seconds, limit)     # type: ignore[union-attr]
        allowed, count = await self._guard(_run)
        return (bool(allowed), int(count))

    # ---------- simple distributed lock ----------

    _UNLOCK_LUA = """
    -- KEY[1] = lock key
    -- ARGV[1] = expected owner token
    local v = redis.call('GET', KEYS[1])
    if v == ARGV[1] then
      return redis.call('DEL', KEYS[1])
    else
      return 0
    end
    """

    async def acquire_lock(self, key: str, owner_token: str, ttl_seconds: int) -> bool:
        """SET NX + EX lock."""
        return await self._guard(lambda: self.redis.set(key, owner_token, nx=True, ex=ttl_seconds))  # type: ignore[union-attr]

    async def release_lock(self, key: str, owner_token: str) -> bool:
        """Unlock only if we own it (atomic check & delete)."""
        async def _run():
            try:
                return await self.redis.evalsha(self._unlock_sha, 1, key, owner_token)  # type: ignore[union-attr]
            except RedisError:
                return await self.redis.eval(self._UNLOCK_LUA, 1, key, owner_token)     # type: ignore[union-attr]
        return (await self._guard(_run)) == 1

    # ---------- tenant-scoped key builders ----------

    def tenant_session_key(self, tenant_id: UUID, user_id: UUID) -> str:
        return self._k("tenant", tenant_id, "session", user_id)

    def rate_limit_key(self, tenant_id: UUID, endpoint: str) -> str:
        return self._k("ratelimit", tenant_id, slugify(endpoint))

    def cache_key(self, tenant_id: UUID, object_type: str, object_id: str | UUID) -> str:
        return self._k("cache", tenant_id, slugify(object_type), object_id)

    def idempotency_key(self, tenant_id: UUID, scope: str, token: str) -> str:
        return self._k("idem", tenant_id, slugify(scope), token)

# Global instance
redis_client = RedisClient()

async def get_redis() -> RedisClient:
    await redis_client.ensure_connected()
    return redis_client
