"""
Rate limiter protocol for domain layer.
Abstracts rate limiting without coupling to infrastructure.
"""
from abc import ABC, abstractmethod

class RateLimiter(ABC):
    """Rate limiter interface."""
    
    @abstractmethod
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 1
    ) -> bool:
        """Check if action is within rate limit."""
        pass
    
    @abstractmethod
    async def consume_token(
        self,
        key: str,
        tokens: int = 1
    ) -> bool:
        """Consume tokens from rate limit bucket."""
        pass
    
    @abstractmethod
    async def get_remaining_tokens(self, key: str) -> int:
        """Get remaining tokens in bucket."""
        pass