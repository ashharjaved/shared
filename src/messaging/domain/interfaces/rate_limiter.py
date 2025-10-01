"""
Rate limiter protocol for domain layer.
Abstracts rate limiting without coupling to infrastructure.
"""
from typing import Protocol, Tuple
from uuid import UUID


class RateLimiter(Protocol):
    """Protocol for rate limiting operations."""
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int = 1,
        burst: int | None = None
    ) -> Tuple[bool, int]:
        """
        Check if action is allowed under rate limit.
        
        Args:
            key: Unique identifier for rate limit bucket (e.g., "channel:{id}")
            limit: Maximum requests per window
            window_seconds: Time window in seconds (default 1s)
            burst: Optional burst capacity (default = limit * 2)
        
        Returns:
            Tuple of (allowed: bool, remaining_tokens: int)
        """
        ...
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for given key."""
        ...
    
    async def get_usage(self, key: str) -> int:
        """Get current usage count for key."""
        ...