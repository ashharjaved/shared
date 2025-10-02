"""
Idempotency Checker using Redis
Prevents duplicate message processing.
"""
from typing import Optional
from uuid import UUID

from shared.infrastructure.cache.redis_cache import RedisCache
from src.messaging.domain.exceptions import DuplicateMessageError
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class IdempotencyChecker:
    """
    Redis-based idempotency checker for WhatsApp messages.
    
    Uses wa_message_id as idempotency key.
    """
    
    def __init__(self, redis: RedisCache):
        self.redis = redis
    
    async def check_and_mark(
        self,
        wa_message_id: str,
        ttl: int = 86400  # 24 hours
    ) -> None:
        """
        Check if message already processed and mark as processed.
        
        Args:
            wa_message_id: WhatsApp message ID
            ttl: Key expiry in seconds
        
        Raises:
            DuplicateMessageError: If message already processed
        """
        key = f"idempotency:wa_message:{wa_message_id}"
        
        # Try to set key with NX (only if not exists)
        result = await self.redis.set(key, "1", ttl=ttl)
        
        if not result:
            logger.warning(
                f"Duplicate message detected: {wa_message_id}",
                extra={"wa_message_id": wa_message_id}
            )
            raise DuplicateMessageError(f"Message {wa_message_id} already processed")
        
        logger.debug(f"Message marked as processed: {wa_message_id}")
    
    async def is_processed(self, wa_message_id: str) -> bool:
        """Check if message was already processed."""
        key = f"idempotency:wa_message:{wa_message_id}"
        result = await self.redis.get(key)
        return result is not None