"""Redis cache implementation for messaging module."""

import json
import logging
from typing import Optional, Any, Dict, Union
import redis.asyncio as redis
from datetime import timedelta

logger = logging.getLogger(__name__)


class MessagingCache:
    """Cache implementation for messaging module."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.default_ttl = 300  # 5 minutes
    
    # Channel caching
    async def get_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get cached channel data."""
        key = f"channel:{channel_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_channel(self, channel_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Cache channel data."""
        key = f"channel:{channel_id}"
        effective_ttl = ttl or self.default_ttl
        await self.redis.setex(key, effective_ttl, json.dumps(data))
    
    async def delete_channel(self, channel_id: str) -> None:
        """Remove channel from cache."""
        key = f"channel:{channel_id}"
        await self.redis.delete(key)
    
    # Template caching
    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get cached template data."""
        key = f"template:{template_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_template(self, template_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Cache template data."""
        key = f"template:{template_id}"
        effective_ttl = ttl or self.default_ttl
        await self.redis.setex(key, effective_ttl, json.dumps(data))
    
    async def list_templates_by_channel(self, channel_id: str) -> Optional[list]:
        """Get cached template list for channel."""
        key = f"templates:channel:{channel_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_templates_by_channel(self, channel_id: str, templates: list, ttl: Optional[int] = None) -> None:
        """Cache template list for channel."""
        key = f"templates:channel:{channel_id}"
        effective_ttl = ttl or self.default_ttl
        await self.redis.setex(key, effective_ttl, json.dumps(templates))
    
    # Session management
    async def get_session_window(self, phone_number: str) -> Optional[str]:
        """Get last inbound timestamp for session window."""
        key = f"session:{phone_number}"
        return await self.redis.get(key)
    
    async def set_session_window(self, phone_number: str, timestamp: str) -> None:
        """Set last inbound timestamp for session window."""
        key = f"session:{phone_number}"
        ttl = 86400  # 24 hours
        await self.redis.setex(key, ttl, timestamp)
    
    # Idempotency
    async def check_idempotency(self, key: str) -> bool:
        """Check if operation was already processed."""
        full_key = f"idempotent:{key}"
        result = await self.redis.set(full_key, "1", nx=True, ex=3600)
        return bool(result)
    
    # Webhook deduplication
    async def is_webhook_processed(self, message_id: str) -> bool:
        """Check if webhook message was already processed."""
        key = f"webhook:processed:{message_id}"
        result = await self.redis.set(key, "1", nx=True, ex=3600)
        return not bool(result)  # Return True if already processed
    
    # Rate limit info caching
    async def get_rate_limit_info(self, channel_id: str) -> Optional[Dict[str, Union[int, float]]]:
        """Get rate limit info for channel."""
        key = f"ratelimit:info:{channel_id}"
        tokens = await self.redis.get(f"{key}:tokens")
        last_refill = await self.redis.get(f"{key}:last_refill")
        
        if tokens and last_refill:
            return {
                "tokens": int(tokens),
                "last_refill": float(last_refill)
            }
        return None
    
    async def set_rate_limit_info(self, channel_id: str, tokens: int, last_refill: float) -> None:
        """Set rate limit info for channel."""
        key = f"ratelimit:info:{channel_id}"
        await self.redis.setex(f"{key}:tokens", 60, str(tokens))
        await self.redis.setex(f"{key}:last_refill", 60, str(last_refill))