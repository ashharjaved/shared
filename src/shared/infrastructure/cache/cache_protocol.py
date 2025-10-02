"""
Cache Protocol (Abstract Interface)
Contract for all cache implementations
"""
from __future__ import annotations

from typing import Any, Protocol


class ICacheProvider(Protocol):
    """
    Abstract cache provider interface.
    
    All cache implementations (Redis, Memcached, etc.) must conform to this protocol.
    Cache is used ONLY for optimization - never as source of truth.
    """
    
    async def get(self, key: str) -> Any | None:
        """
        Retrieve value from cache by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        ...
    
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
            value: Value to cache (must be serializable)
            ttl: Time-to-live in seconds (None for no expiration)
            
        Returns:
            True if successful, False otherwise
        """
        ...
    
    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key existed and was deleted, False otherwise
        """
        ...
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        ...
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment
        """
        ...
    
    async def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrement a numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to decrement by
            
        Returns:
            New value after decrement
        """
        ...
    
    async def set_many(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """
        Set multiple key-value pairs at once.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time-to-live in seconds
            
        Returns:
            True if all successful, False otherwise
        """
        ...
    
    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        Get multiple values by keys.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs (missing keys omitted)
        """
        ...
    
    async def clear(self) -> bool:
        """
        Clear all keys from cache (use with caution).
        
        Returns:
            True if successful, False otherwise
        """
        ...
    
    async def ping(self) -> bool:
        """
        Ping the cache to check connectivity.
        
        Returns:
            True if cache is reachable, False otherwise
        """
        ...