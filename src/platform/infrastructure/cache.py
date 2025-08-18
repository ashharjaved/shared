# src/platform/infrastructure/cache.py
import time
from threading import RLock
from typing import Any, Optional
from uuid import UUID

from src.config import settings


class InMemoryTTLCache:
    """
    Simple in-process TTL cache. Keyed by (tenant_id, key) -> (value, expires_at).
    Not multi-process safe; suitable for MVP only.
    """

    def __init__(self, ttl_seconds: int = 30):
        self._store: dict[tuple[str, str], tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._lock = RLock()

    def get(self, tenant_id: UUID, key: str) -> Optional[Any]:
        now = time.monotonic()
        k = (tenant_id, key)
        with self._lock:
            entry = self._store.get((tenant_id, key))
            if not entry:
                return None
            value, exp = entry
            if now >= exp:
                with self._lock:
                    self._store.pop((tenant_id, key), None)
                return None
            return value

    def set(self, tenant_id: UUID, key: str, value: Any) -> None:
        k = (tenant_id, key)
        cache_key = f"tenant:{tenant_id}:config:{key}"
        self._cache[cache_key] = {
             "value": value,
             "expires_at": time.time() + self.ttl_seconds
        }
        
    def invalidate(self, tenant_id: str, key: str) -> None:
        with self._lock:
            self._store.pop((tenant_id, key), None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# Singleton cache instance (MVP)
_cache_instance: Optional[InMemoryTTLCache] = None


def _get_cache() -> InMemoryTTLCache:
    """Return a per-process cache configured with CONFIG_TTL_SECONDS."""
    global _cache_instance
    if _cache_instance is None or _cache_instance._ttl != settings.CONFIG_TTL_SECONDS:
        _cache_instance = InMemoryTTLCache(settings.CONFIG_TTL_SECONDS)
    return _cache_instance

def get_cache(ttl_seconds: int) -> InMemoryTTLCache:
    """Return a process-local cache instance; recreated when TTL changes."""
    global _cache_instance
    if _cache_instance is None or _cache_instance._ttl != ttl_seconds:
        _cache_instance = InMemoryTTLCache(ttl_seconds)
    return _cache_instance

# Module-level helpers used across the app
def get_cached(tenant_id: UUID, key: str) -> Optional[Any]:
    return get_cache(ttl_seconds=30).get(tenant_id, key)  # default used unless caller sets explicitly

def set_cached(tenant_id: UUID, key: str, value: Any) -> None:
    get_cache(ttl_seconds=30).set(tenant_id, key, value)


def invalidate(tenant_id: UUID, key: str) -> None:
    c = get_cache(ttl_seconds=30)
    if key:
        with c._lock:
            c._store.pop((str(tenant_id), key), None)
    else:
        with c._lock:
            prefix = str(tenant_id)
            for k in [k for k in list(c._store.keys()) if k[0] == prefix]:
                c._store.pop(k, None)


__all__ = ["InMemoryTTLCache", "get_cache", "get_cached", "set_cached", "invalidate"]
