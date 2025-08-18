import time
from typing import Any, Tuple

class InMemoryTTLCache:
    """
    Simple in-process TTL cache. Keyed by (tenant_id, key) -> (value, expires_at).
    Not multi-process safe; suitable for MVP only.
    """
    def __init__(self, ttl_seconds: int = 30):
        self._store: dict[Tuple[str, str], Tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, tenant_id: str, key: str) -> Any | None:
        now = time.time()
        entry = self._store.get((tenant_id, key))
        if not entry:
            return None
        value, exp = entry
        if now >= exp:
            self._store.pop((tenant_id, key), None)
            return None
        return value

    def set(self, tenant_id: str, key: str, value: Any) -> None:
        self._store[(tenant_id, key)] = (value, time.time() + self._ttl)

    def invalidate(self, tenant_id: str, key: str) -> None:
        self._store.pop((tenant_id, key), None)

# Singleton-ish cache for the process (MVP)
_cache_instance: InMemoryTTLCache | None = None

def get_cache(ttl_seconds: int) -> InMemoryTTLCache:
    global _cache_instance
    if _cache_instance is None or _cache_instance._ttl != ttl_seconds:
        _cache_instance = InMemoryTTLCache(ttl_seconds)
    return _cache_instance
