"""Token bucket rate limiter using Redis."""

import time
from typing import Optional, Tuple
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter implementation using Redis.
    Allows burst traffic up to bucket capacity.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def is_allowed(
        self,
        key: str,
        rate: int,  # Tokens per second
        burst: Optional[int] = None,
        ttl: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if request is allowed based on token bucket.
        Returns (allowed, tokens_remaining).
        """
        if burst is None:
            burst = rate * 2  # Default burst is 2x rate
        
        now = time.time()
        bucket_key = f"ratelimit:{key}"
        
        # Lua script for atomic token bucket operations
        lua_script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local burst = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local ttl = tonumber(ARGV[4])
        
        local bucket = redis.call('HGETALL', key)
        local tokens = burst
        local last_refill = now
        
        if #bucket > 0 then
            -- Parse existing bucket
            for i = 1, #bucket, 2 do
                if bucket[i] == 'tokens' then
                    tokens = tonumber(bucket[i + 1])
                elseif bucket[i] == 'last_refill' then
                    last_refill = tonumber(bucket[i + 1])
                end
            end
            
            -- Calculate tokens to add based on time passed
            local time_passed = now - last_refill
            local tokens_to_add = time_passed * rate
            tokens = math.min(burst, tokens + tokens_to_add)
        end
        
        local allowed = 0
        if tokens >= 1 then
            tokens = tokens - 1
            allowed = 1
        end
        
        -- Update bucket
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        return {allowed, math.floor(tokens)}
        """
        
        try:
            result = await self.redis.eval(
                lua_script,
                1,
                bucket_key,
                rate,
                burst,
                now,
                ttl
            )
            
            allowed = bool(result[0])
            tokens_remaining = int(result[1])
            
            if not allowed:
                logger.warning(f"Rate limit exceeded for key {key}")
            
            return allowed, tokens_remaining
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # On error, allow the request but log it
            return True, 0
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        bucket_key = f"ratelimit:{key}"
        await self.redis.delete(bucket_key)