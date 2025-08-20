# # src/platform/infrastructure/cache.py
# import time
# from threading import RLock
# from typing import Any, Optional
# from uuid import UUID

# from src.config import settings


# class InMemoryTTLCache:
#     """
#     Simple in-process TTL cache. Keyed by (tenant_id, key) -> (value, expires_at).
#     Not multi-process safe; suitable for MVP only.
#     """

#     def __init__(self, ttl_seconds: int = 30):
#         self._store: dict[tuple[str, str], tuple[Any, float]] = {}
#         self._ttl = ttl_seconds
#         self._lock = RLock()

#     def get(self, tenant_id: UUID, key: str) -> Optional[Any]:
#         now = time.monotonic()
#         k = (tenant_id, key)
#         with self._lock:
#             entry = self._store.get((tenant_id, key))
#             if not entry:
#                 return None
#             value, exp = entry
#             if now >= exp:
#                 with self._lock:
#                     self._store.pop((tenant_id, key), None)
#                 return None
#             return value

#     def set(self, tenant_id: UUID, key: str, value: Any) -> None:
#         k = (tenant_id, key)
#         cache_key = f"tenant:{tenant_id}:config:{key}"
#         self._cache[cache_key] = {
#              "value": value,
#              "expires_at": time.time() + self.ttl_seconds
#         }
        
#     def invalidate(self, tenant_id: str, key: str) -> None:
#         with self._lock:
#             self._store.pop((tenant_id, key), None)

#     def clear(self) -> None:
#         with self._lock:
#             self._store.clear()


# # Singleton cache instance (MVP)
# _cache_instance: Optional[InMemoryTTLCache] = None


# def _get_cache() -> InMemoryTTLCache:
#     """Return a per-process cache configured with CONFIG_TTL_SECONDS."""
#     global _cache_instance
#     if _cache_instance is None or _cache_instance._ttl != settings.CONFIG_TTL_SECONDS:
#         _cache_instance = InMemoryTTLCache(settings.CONFIG_TTL_SECONDS)
#     return _cache_instance

# def get_cache(ttl_seconds: int) -> InMemoryTTLCache:
#     """Return a process-local cache instance; recreated when TTL changes."""
#     global _cache_instance
#     if _cache_instance is None or _cache_instance._ttl != ttl_seconds:
#         _cache_instance = InMemoryTTLCache(ttl_seconds)
#     return _cache_instance

# # Module-level helpers used across the app
# def get_cached(tenant_id: UUID, key: str) -> Optional[Any]:
#     return get_cache(ttl_seconds=settings.CONFIG_TTL_SECONDS).get(tenant_id, key)

# def set_cached(tenant_id: UUID, key: str, value: Any) -> None:
#     get_cache(ttl_seconds=settings.CONFIG_TTL_SECONDS).set(tenant_id, key, value)


# def invalidate(tenant_id: UUID, key: str) -> None:
#     c = get_cache(ttl_seconds=settings.CONFIG_TTL_SECONDS)
#     if key:
#         with c._lock:
#             c._store.pop((str(tenant_id), key), None)
#     else:
#         with c._lock:
#             prefix = str(tenant_id)
#             for k in [k for k in list(c._store.keys()) if k[0] == prefix]:
#                 c._store.pop(k, None)


# __all__ = ["InMemoryTTLCache", "get_cache", "get_cached", "set_cached", "invalidate"]
#--------------------------------------------------------------------------------------------------
from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

from src.config import settings

_TenantKey = Tuple[str, str]  # (tenant_id, key)
_Value = Tuple[Any, float]    # (value, expires_at)

# Single in-process store with a global lock (safe for async/sync access in one process)
_STORE: Dict[_TenantKey, _Value] = {}
_LOCK = threading.Lock()


def _norm_tenant(tenant_id: Union[str, UUID, None]) -> Optional[str]:
    if tenant_id is None:
        return None
    return str(tenant_id)


def _now() -> float:
    return time.monotonic()


def _ttl(default: Optional[int]) -> int:
    if isinstance(default, int) and default > 0:
        return default
    return int(getattr(settings, "CONFIG_TTL_SECONDS", 60)) or 60


def set_cached(
    tenant_id: Union[str, UUID],
    key: str,
    value: Any,
    ttl_seconds: Optional[int] = None,
) -> None:
    """
    Store a value per tenant/key with TTL.
    """
    t = _norm_tenant(tenant_id)
    if t is None or not key:
        return
    expires = _now() + _ttl(ttl_seconds)
    with _LOCK:
        _STORE[(t, key)] = (value, expires)


def get_cached(
    tenant_id: Union[str, UUID, None],
    key: str,
) -> Optional[Any]:
    """
    Retrieve a cached value if present and not expired; otherwise None.
    """
    t = _norm_tenant(tenant_id)
    if t is None or not key:
        return None
    k = (t, key)
    with _LOCK:
        item = _STORE.get(k)
        if not item:
            return None
        value, expires = item
        if _now() >= expires:
            # expired — remove and miss
            _STORE.pop(k, None)
            return None
        return value


def invalidate(tenant_id: Union[str, UUID], key: str) -> None:
    """
    Remove a cached entry explicitly.
    """
    t = _norm_tenant(tenant_id)
    if t is None or not key:
        return
    with _LOCK:
        _STORE.pop((t, key), None)


# Optional: simple facade object if you prefer an instance API
class _CacheFacade:
    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        self._ttl = _ttl(ttl_seconds)

    def get(self, tenant_id: Union[str, UUID, None], key: str) -> Optional[Any]:
        return get_cached(tenant_id, key)

    def set(self, tenant_id: Union[str, UUID], key: str, value: Any) -> None:
        set_cached(tenant_id, key, value, ttl_seconds=self._ttl)

    def invalidate(self, tenant_id: Union[str, UUID], key: str) -> None:
        invalidate(tenant_id, key)


def get_cache(ttl_seconds: Optional[int] = None) -> _CacheFacade:
    """
    Returns a lightweight facade honoring a fixed TTL for set() calls.
    Existing code can do:
        c = get_cache()
        c.set(tenant_id, "whatsapp.app_secret", "secret")
        c.get(tenant_id, "whatsapp.app_secret")
    """
    return _CacheFacade(ttl_seconds=ttl_seconds)
