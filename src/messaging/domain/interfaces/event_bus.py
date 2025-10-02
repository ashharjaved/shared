"""
Event bus protocol for domain events.
Abstracts event publishing without infrastructure dependencies.
"""
from typing import Protocol
from src.messaging.domain.events.message_events import DomainEvent


class EventBus(Protocol):
    """Protocol for publishing domain events."""
    
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event.
        
        Args:
            event: Domain event to publish
        """
        ...
    
    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple events atomically.
        
        Args:
            events: List of domain events
        """
        ...