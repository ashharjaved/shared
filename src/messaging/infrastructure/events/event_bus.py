"""Event bus for publishing domain events."""

import json
import logging
from typing import Any, Dict, List
import redis.asyncio as redis
from dataclasses import asdict

from src.messaging.domain.events.message_events import DomainEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Event bus implementation using Redis pub/sub."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.subscribers: Dict[str, List[callable]] = {}
    
    async def publish(self, event: DomainEvent) -> None:
        """Publish domain event."""
        try:
            # Convert event to dict
            event_data = {
                "event_id": str(event.event_id),
                "aggregate_id": str(event.aggregate_id),
                "tenant_id": str(event.tenant_id),
                "event_type": event.event_type,
                "occurred_at": event.occurred_at.isoformat(),
                "metadata": event.metadata or {}
            }
            
            # Add event-specific data
            for key, value in asdict(event).items():
                if key not in event_data:
                    if hasattr(value, '__dict__'):
                        event_data[key] = str(value)
                    else:
                        event_data[key] = value
            
            # Publish to Redis channel
            channel = f"events:{event.event_type}"
            message = json.dumps(event_data)
            
            await self.redis.publish(channel, message)
            
            # Also save to event store for durability
            await self._save_to_event_store(event_data)
            
            logger.info(f"Published event {event.event_type} for aggregate {event.aggregate_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise
    
    async def subscribe(self, event_type: str, handler: callable) -> None:
        """Subscribe to event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        
        # Start listening to Redis channel
        channel = f"events:{event_type}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        
        logger.info(f"Subscribed to event type {event_type}")
    
    async def _save_to_event_store(self, event_data: Dict[str, Any]) -> None:
        """Save event to persistent store."""
        try:
            # Save to a sorted set for event sourcing
            key = f"eventstore:{event_data['tenant_id']}:{event_data['aggregate_id']}"
            score = event_data['occurred_at']
            
            await self.redis.zadd(
                key,
                {json.dumps(event_data): score}
            )
            
            # Set TTL for 30 days
            await self.redis.expire(key, 2592000)
            
        except Exception as e:
            logger.error(f"Failed to save event to store: {e}")