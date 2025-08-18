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


# Module-level helpers used across the app
def get_cached(tenant_id: UUID, key: str) -> Optional[Any]:
    return _get_cache().get(tenant_id, key)


def set_cached(tenant_id: UUID, key: str, value: Any) -> None:
    cache_key = f"tenant:{tenant_id}:config:{key}"
    _get_cache().set(tenant_id, key, value)


def invalidate(tenant_id: UUID, key: str) -> None:
    if key:
        self._cache.pop(f"tenant:{tenant_id}:config:{key}", None)
    else:
        # Invalidate all config keys for tenant
            tenant_prefix = f"tenant:{tenant_id}:config:"
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(tenant_prefix)]
            for k in keys_to_remove:
                self._cache.pop(k, None)
    #_get_cache().invalidate(tenant_id, key)


__all__ = ["InMemoryTTLCache", "get_cached", "set_cached", "invalidate"]
