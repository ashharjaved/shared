"""
Event bus protocol for domain events.
Abstracts event publishing without infrastructure dependencies.
"""
from typing import Protocol, Any
from src.messaging.domain.events.base_event import DomainEvent


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