"""
Redis Cache Implementation
Async Redis-based cache provider
"""
from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class RedisCache:
    """
    Async Redis cache implementation.
    
    Uses Redis for caching, session storage, rate limiting, and distributed locks.
    CRITICAL: Redis is ONLY for optimization - never source of truth.
    
    Attributes:
        redis: Async Redis client
        key_prefix: Prefix for all cache keys (for namespacing)
    """
    
    def __init__(self, redis: Redis, key_prefix: str = "chatbot") -> None:
        """
        Initialize Redis cache.
        
        Args:
            redis: Async Redis client instance
            key_prefix: Prefix for cache keys (default: "chatbot")
        """
        self.redis = redis
        self.key_prefix = key_prefix
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key for namespacing."""
        return f"{self.key_prefix}:{key}"
    
    async def get(self, key: str) -> Any | None:
        """
        Retrieve value from cache by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value (deserialized) or None
        """
        try:
            value = await self.redis.get(self._make_key(key))
            if value is None:
                return None
            
            # Deserialize JSON
            return json.loads(value)
        except RedisError as e:
            logger.error(
                "Redis GET failed",
                extra={"key": key, "error": str(e)},
            )
            return None
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to deserialize cached value",
                extra={"key": key, "error": str(e)},
            )
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Serialize to JSON
            serialized = json.dumps(value)
            
            if ttl:
                await self.redis.setex(self._make_key(key), ttl, serialized)
            else:
                await self.redis.set(self._make_key(key), serialized)
            
            logger.debug(
                "Cached value",
                extra={"key": key, "ttl": ttl},
            )
            return True
        except (RedisError, TypeError, ValueError) as e:
            logger.error(
                "Redis SET failed",
                extra={"key": key, "error": str(e)},
            )
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key existed and was deleted
        """
        try:
            result = await self.redis.delete(self._make_key(key))
            return result > 0
        except RedisError as e:
            logger.error(
                "Redis DELETE failed",
                extra={"key": key, "error": str(e)},
            )
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists
        """
        try:
            result = await self.redis.exists(self._make_key(key))
            return result > 0
        except RedisError as e:
            logger.error(
                "Redis EXISTS failed",
                extra={"key": key, "error": str(e)},
            )
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment
        """
        try:
            return await self.redis.incrby(self._make_key(key), amount)
        except RedisError as e:
            logger.error(
                "Redis INCR failed",
                extra={"key": key, "error": str(e)},
            )
            raise
    
    async def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrement a numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to decrement by
            
        Returns:
            New value after decrement
        """
        try:
            return await self.redis.decrby(self._make_key(key), amount)
        except RedisError as e:
            logger.error(
                "Redis DECR failed",
                extra={"key": key, "error": str(e)},
            )
            raise
    
    async def set_many(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """
        Set multiple key-value pairs at once.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time-to-live in seconds
            
        Returns:
            True if all successful
        """
        try:
            pipeline = self.redis.pipeline()
            
            for key, value in mapping.items():
                serialized = json.dumps(value)
                if ttl:
                    pipeline.setex(self._make_key(key), ttl, serialized)
                else:
                    pipeline.set(self._make_key(key), serialized)
            
            await pipeline.execute()
            return True
        except (RedisError, TypeError, ValueError) as e:
            logger.error(
                "Redis MSET failed",
                extra={"count": len(mapping), "error": str(e)},
            )
            return False
    
    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        Get multiple values by keys.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs (missing keys omitted)
        """
        try:
            prefixed_keys = [self._make_key(k) for k in keys]
            values = await self.redis.mget(prefixed_keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Failed to deserialize cached value",
                            extra={"key": key},
                        )
            
            return result
        except RedisError as e:
            logger.error(
                "Redis MGET failed",
                extra={"count": len(keys), "error": str(e)},
            )
            return {}
    
    async def clear(self) -> bool:
        """
        Clear all keys with this prefix (use with caution).
        
        Returns:
            True if successful
        """
        try:
            pattern = f"{self.key_prefix}:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                
                if keys:
                    await self.redis.delete(*keys)
                
                if cursor == 0:
                    break
            
            logger.warning("Cache cleared", extra={"prefix": self.key_prefix})
            return True
        except RedisError as e:
            logger.error(
                "Redis CLEAR failed",
                extra={"error": str(e)},
            )
            return False
    
    async def ping(self) -> bool:
        """
        Ping Redis to check connectivity.
        
        Returns:
            True if Redis is reachable
        """
        try:
            await self.redis.ping()
            return True
        except RedisError as e:
            logger.error(
                "Redis PING failed",
                extra={"error": str(e)},
            )
            return False