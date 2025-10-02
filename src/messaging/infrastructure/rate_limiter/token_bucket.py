# src/modules/whatsapp/infrastructure/rate_limiting/token_bucket.py
"""
Token Bucket Rate Limiter using Redis
"""
import time
from typing import Optional
from uuid import UUID

from redis.asyncio import Redis

from messaging.domain.exceptions import RateLimitExceededError
from src.shared.infrastructure.observability.logger import get_logger


logger = get_logger(__name__)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for WhatsApp message sending.
    
    Uses Redis for distributed rate limiting across workers.
    Default: 80 messages per second per phone number (WhatsApp limit).
    
    Algorithm:
    1. Bucket starts with max_tokens
    2. Each send consumes 1 token
    3. Tokens refill at refill_rate per second
    4. If bucket empty, reject request
    """
    
    def __init__(
        self,
        redis: Redis,
        max_tokens: int = 80,
        refill_rate: float = 80.0,
    ) -> None:
        """
        Initialize rate limiter.
        
        Args:
            redis: Redis client
            max_tokens: Bucket capacity
            refill_rate: Tokens per second refill rate
        """
        self.redis = redis
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
    
    def _get_key(self, tenant_id: UUID, phone_number_id: str) -> str:
        """
        Get Redis key for rate limit bucket.
        
        Args:
            tenant_id: Tenant UUID
            phone_number_id: WhatsApp phone number ID
            
        Returns:
            Redis key
        """
        return f"rate_limit:whatsapp:{tenant_id}:{phone_number_id}"
    
    async def acquire(
        self,
        tenant_id: UUID,
        phone_number_id: str,
        tokens: int = 1,
    ) -> bool:
        """
        Attempt to acquire tokens from bucket.
        
        Args:
            tenant_id: Tenant UUID
            phone_number_id: WhatsApp phone number ID
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens acquired, False if rate limited
            
        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        key = self._get_key(tenant_id, phone_number_id)
        now = time.time()
        
        # Lua script for atomic token bucket operation
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or max_tokens
        local last_refill = tonumber(bucket[2]) or now
        
        -- Refill tokens based on elapsed time
        local elapsed = now - last_refill
        local tokens_to_add = elapsed * refill_rate
        tokens = math.min(max_tokens, tokens + tokens_to_add)
        
        -- Check if enough tokens available
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 10)
            return 1
        else
            -- Not enough tokens
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 10)
            return 0
        end
        """
        
        result = self.redis.eval(
            lua_script,
            1,
            key,
            self.max_tokens,
            self.refill_rate,
            tokens,
            now,
        )
        
        if result == 1:
            logger.debug(
                f"Rate limit acquired: {tokens} token(s)",
                extra={
                    "tenant_id": str(tenant_id),
                    "phone_number_id": phone_number_id,
                },
            )
            return True
        else:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "tenant_id": str(tenant_id),
                    "phone_number_id": phone_number_id,
                    "tokens_requested": tokens,
                },
            )
            raise RateLimitExceededError(
                f"Rate limit exceeded for phone number {phone_number_id}"
            )
    
    async def get_remaining_tokens(
        self,
        tenant_id: UUID,
        phone_number_id: str,
    ) -> float:
        """
        Get remaining tokens in bucket.
        
        Args:
            tenant_id: Tenant UUID
            phone_number_id: WhatsApp phone number ID
            
        Returns:
            Remaining tokens
        """
        key = self._get_key(tenant_id, phone_number_id)
        now = time.time()
        
        bucket = await self.redis.hmget(key, "tokens", "last_refill")
        
        if not bucket[0]:
            return float(self.max_tokens)
        
        tokens = float(bucket[0])
        last_refill = float(bucket[1])
        
        # Calculate refilled tokens
        elapsed = now - last_refill
        tokens_to_add = elapsed * self.refill_rate
        current_tokens = min(self.max_tokens, tokens + tokens_to_add)
        
        return current_tokens