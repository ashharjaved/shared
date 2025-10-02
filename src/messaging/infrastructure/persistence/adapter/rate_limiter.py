"""Rate limiter implementation using Redis."""

import asyncio
from datetime import datetime

from shared.infrastructure.cache.redis_cache import RedisCache
from src.messaging.domain.protocols import RateLimiter
from shared.infrastructure.observability.logger import get_logger
from shared.infrastructure.observability.metrics import get_metrics

logger = get_logger(__name__)


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiter implementation using Redis."""
    
    def __init__(self, redis_cache: RedisCache):
        self.redis = redis_cache
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 1
    ) -> bool:
        """Check if action is within rate limit."""
        bucket_key = f"rate_limit:token_bucket:{key}"
        timestamp_key = f"rate_limit:timestamp:{key}"
        
        # Get current timestamp
        now = datetime.utcnow().timestamp()
        
        # Get last refill timestamp
        last_refill = await self.redis.get(timestamp_key)
        last_refill = float(last_refill) if last_refill else now
        
        # Calculate tokens to add based on time passed
        time_passed = now - last_refill
        tokens_to_add = int(time_passed * (limit / window_seconds))
        
        if tokens_to_add > 0:
            # Refill bucket
            current_tokens = await self.redis.get(bucket_key)
            current_tokens = int(current_tokens) if current_tokens else limit
            
            new_tokens = min(limit, current_tokens + tokens_to_add)
            
            # Update bucket and timestamp atomically
            await self.redis.set(bucket_key, str(new_tokens), ttl=window_seconds * 2)
            await self.redis.set(timestamp_key, str(now), ttl=window_seconds * 2)
            
            return new_tokens > 0
        else:
            # Check if we have tokens
            current_tokens = await self.redis.get(bucket_key)
            return int(current_tokens) > 0 if current_tokens else False
    
    async def consume_token(
        self,
        key: str,
        tokens: int = 1
    ) -> bool:
        """Consume tokens from rate limit bucket."""
        bucket_key = f"rate_limit:token_bucket:{key}"
        
        # Try to decrement tokens
        current = await self.redis.get(bucket_key)
        if not current:
            return False
        
        current_tokens = int(current)
        if current_tokens >= tokens:
            new_value = current_tokens - tokens
            await self.redis.set(bucket_key, str(new_value))
            
            # Track metric
            get_metrics.track_counter(
                "rate_limit_tokens_consumed",
                tokens,
                {"key": key}
            )
            
            return True
        
        # Track rate limit exceeded
        get_metrics.track_counter(
            "rate_limit_exceeded",
            1,
            {"key": key}
        )
        
        return False
    
    async def get_remaining_tokens(self, key: str) -> int:
        """Get remaining tokens in bucket."""
        bucket_key = f"rate_limit:token_bucket:{key}"
        current = await self.redis.get(bucket_key)
        return int(current) if current else 0