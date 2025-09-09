"""Rate limiting policy enforcement for messaging."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from ..types import TenantId, ChannelId


class RateLimitCounter(Protocol):
    """Protocol for rate limit counter storage."""
    
    def get_count(self, key: str, window_start: datetime, window_end: datetime) -> int:
        """Get current count for key within time window."""
        ...
    
    def increment(self, key: str, window_end: datetime) -> int:
        """Increment counter and return new value."""
        ...


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    current_count: int
    limit: int
    retry_after_seconds: int | None = None


class RateLimitPolicy:
    """
    Domain service for rate limiting enforcement.
    
    Enforces per-tenant and per-channel rate limits using sliding windows.
    Does not contain infrastructure concerns - uses injected counter.
    
    Example:
        policy = RateLimitPolicy(counter)
        result = policy.check_per_tenant(tenant_id, 100, timedelta(minutes=1))
        if not result.allowed:
            raise RateLimited("Rate limit exceeded", result.retry_after_seconds)
    """
    
    def __init__(self, counter: RateLimitCounter) -> None:
        self._counter = counter
    
    def check_per_tenant(
        self, 
        tenant_id: TenantId, 
        count: int, 
        window: timedelta
    ) -> RateLimitResult:
        """
        Check if tenant is within rate limit for given window.
        
        Args:
            tenant_id: Tenant to check
            count: Maximum allowed operations in window
            window: Time window duration
            
        Returns:
            RateLimitResult with allow/deny decision
        """
        key = f"rate_limit:tenant:{tenant_id}"
        return self._check_limit(key, count, window)
    
    def check_per_channel(
        self,
        channel_id: ChannelId,
        count: int, 
        window: timedelta
    ) -> RateLimitResult:
        """
        Check if channel is within rate limit for given window.
        
        Args:
            channel_id: Channel to check
            count: Maximum allowed operations in window
            window: Time window duration
            
        Returns:
            RateLimitResult with allow/deny decision
        """
        key = f"rate_limit:channel:{channel_id}"
        return self._check_limit(key, count, window)
    
    def _check_limit(self, key: str, limit: int, window: timedelta) -> RateLimitResult:
        """Internal rate limit check implementation."""
        now = datetime.utcnow()
        window_start = now - window
        
        current_count = self._counter.get_count(key, window_start, now)
        
        if current_count >= limit:
            # Calculate retry after based on window duration
            retry_after = int(window.total_seconds())
            return RateLimitResult(
                allowed=False,
                current_count=current_count,
                limit=limit,
                retry_after_seconds=retry_after
            )
        
        # Increment and allow
        new_count = self._counter.increment(key, now + window)
        return RateLimitResult(
            allowed=True,
            current_count=new_count,
            limit=limit
        )