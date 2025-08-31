from __future__ import annotations

from typing import Iterable

from src.platform.infrastructure.cache.redis_client import RedisClient


class CacheInvalidationService:
    """
    Targeted cache invalidation for configuration keys.
    Keys:
      - cfg:{tenant_id}:{config_key}
    TTL policy is managed at write; invalidation deletes the key immediately.
    """

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def invalidate_key(self, tenant_id: str, key: str) -> None:
        await self._redis.delete(f"cfg:{tenant_id}:{key}")

    async def invalidate_many(self, tenant_id: str, keys: Iterable[str]) -> None:
        for k in keys:
            await self.invalidate_key(tenant_id, k)
