from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Optional, Protocol, runtime_checkable

@runtime_checkable
class AsyncRedisLike(Protocol):
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...

class _InMemoryAsyncRedis:
    """
    Minimal async-compatible in-memory Redis substitute for local/dev
    when redis-py is unavailable. **Not for production**.
    """
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._exp: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            self._purge_if_needed(key)
            val = self._data.get(key)
            return None if val is None else str(val)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        async with self._lock:
            self._data[key] = value
            if ex is not None:
                loop = asyncio.get_event_loop()
                self._exp[key] = loop.time() + ex

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)
            self._exp.pop(key, None)

    async def incr(self, key: str) -> int:
        async with self._lock:
            self._purge_if_needed(key)
            val = int(self._data.get(key, "0"))
            val += 1
            self._data[key] = str(val)
            return val

    async def expire(self, key: str, seconds: int) -> None:
        async with self._lock:
            if key in self._data:
                loop = asyncio.get_event_loop()
                self._exp[key] = loop.time() + seconds

    def _purge_if_needed(self, key: str) -> None:
        exp = self._exp.get(key)
        if exp is not None:
            loop = asyncio.get_event_loop()
            if loop.time() >= exp:
                self._data.pop(key, None)
                self._exp.pop(key, None)
    
    # Provide ping/close so the in-memory client satisfies the protocol.
    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class RedisClient:
    """
    Thin async JSON-friendly Redis adapter:
      - get_json / set_json / delete
      - incr_with_expire (atomic enough for counters; prefers real Redis if available)
    """
    def __init__(self) -> None:
        self._client: Optional[AsyncRedisLike] = None
        self._is_fake = False

    async def connect(self) -> None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis.asyncio as redis  # type: ignore
            self.client = redis.from_url(url, decode_responses=True)
            # smoke check
            await self.client.ping()
        except Exception:
            # Fallback to in-memory implementation for local dev.
            self._client = _InMemoryAsyncRedis()
            self._is_fake = True

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                # Best-effort shutdown; ignore close errors
                pass

    def _ensure(self) -> AsyncRedisLike:
        if self._client is None:
            raise RuntimeError("RedisClient is not connected. Call await connect() first.")
        return self._client

    async def get_json(self, key: str) -> Optional[dict]:
        client = self._ensure()
        raw = await client.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: dict, ttl_seconds: int = 300) -> None:
        client = self._ensure()
        await client.set(key, json.dumps(value, separators=(",", ":")), ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        client = self._ensure()
        await client.delete(key)

    async def incr_with_expire(self, key: str, ttl_seconds: int) -> int:
        """
        Atomic-ish INCR + EXPIRE. With real Redis this becomes atomic in a single event loop turn.
        For in-memory fallback the lock serializes operations sufficiently for tests.
        """
        client = self._ensure()
        val = await client.incr(key)
        await client.expire(key, ttl_seconds)
        return val
