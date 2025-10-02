"""
Shared Cache Infrastructure
Redis-based caching for optimization only
"""
from shared.infrastructure.cache.cache_protocol import ICacheProvider
from shared.infrastructure.cache.redis_cache import RedisCache

__all__ = [
    "ICacheProvider",
    "RedisCache",
]