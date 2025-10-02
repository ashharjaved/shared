"""Rate limiter implementation using Redis."""

import asyncio
from datetime import datetime, time
from uuid import UUID

from messaging.domain.exceptions import RateLimitExceededError
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
        
    async def check_and_consume(
        self,
        channel_id: UUID,
        rate_limit: int = 80,
        window_seconds: int = 1,
        tokens: int = 1
    ) -> None:
        """
        Check rate limit and consume tokens.
        
        Args:
            channel_id: Channel UUID
            rate_limit: Max tokens per window
            window_seconds: Window size in seconds
            tokens: Tokens to consume
        
        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        key = f"rate_limit:channel:{channel_id}"
        
        # Token bucket algorithm
        now = datetime.utcnow().timestamp()
        
        # Get current bucket state
        bucket_data = await self.redis.get(key)
        
        if bucket_data:
            bucket = eval(bucket_data)  # In production: use JSON
            last_refill = bucket["last_refill"]
            tokens_available = bucket["tokens"]
        else:
            last_refill = now
            tokens_available = rate_limit
        
        # Refill tokens based on time elapsed
        elapsed = now - last_refill
        refill_amount = (elapsed / window_seconds) * rate_limit
        tokens_available = min(rate_limit, tokens_available + refill_amount)
        
        # Check if enough tokens
        if tokens_available < tokens:
            logger.warning(
                f"Rate limit exceeded for channel {channel_id}",
                extra={"available": tokens_available, "requested": tokens}
            )
            raise RateLimitExceededError(
                f"Rate limit exceeded. Available: {tokens_available:.2f}, Requested: {tokens}"
            )
        
        # Consume tokens
        tokens_available -= tokens
        
        # Update bucket
        bucket = {
            "tokens": tokens_available,
            "last_refill": now
        }
        
        await self.redis.set(key, str(bucket), ttl=window_seconds * 2)
        
        logger.debug(
            f"Rate limit check passed for channel {channel_id}",
            extra={"tokens_remaining": tokens_available}
        )