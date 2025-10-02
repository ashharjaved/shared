"""
Domain Event Bus
In-memory event bus for publishing and subscribing to domain events
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from shared.domain.domain_event import DomainEvent
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class EventBus:
    """
    In-memory event bus for domain event publication and subscription.
    
    Allows decoupled communication between modules via domain events.
    Handlers can subscribe to specific event types and react accordingly.
    
    Attributes:
        _handlers: Dictionary mapping event types to handler lists
    """
    
    def __init__(self) -> None:
        """Initialize event bus with empty handler registry."""
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event type.
        
        Args:
            event_type: Fully qualified event class name
            handler: Async callable that accepts the event
            
        Example:
            def handle_user_created(event: UserCreatedEvent):
                # React to event
                pass
            
            event_bus.subscribe("UserCreatedEvent", handle_user_created)
        """
        self._handlers[event_type].append(handler)
        logger.debug(
            f"Handler subscribed to {event_type}",
            extra={"handler": handler.__name__},
        )
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """
        Unsubscribe a handler from an event type.
        
        Args:
            event_type: Event class name
            handler: Handler to remove
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(
                    f"Handler unsubscribed from {event_type}",
                    extra={"handler": handler.__name__},
                )
            except ValueError:
                pass
    
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish a domain event to all subscribed handlers.
        
        Args:
            event: Domain event to publish
        """
        event_type = event.__class__.__name__
        handlers = self._handlers.get(event_type, [])
        
        if not handlers:
            logger.debug(
                f"No handlers for event: {event_type}",
                extra={"event_id": str(event.event_id)},
            )
            return
        
        logger.info(
            f"Publishing event: {event_type}",
            extra={
                "event_id": str(event.event_id),
                "handler_count": len(handlers),
            },
        )
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler failed: {handler.__name__}",
                    extra={
                        "event_type": event_type,
                        "event_id": str(event.event_id),
                        "error": str(e),
                    },
                )
                # Continue processing other handlers even if one fails
    
    async def publish_many(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple domain events.
        
        Args:
            events: List of domain events to publish
        """
        for event in events:
            await self.publish(event)
    
    def clear_handlers(self, event_type: str | None = None) -> None:
        """
        Clear all handlers for an event type, or all handlers.
        
        Args:
            event_type: Event type to clear (None for all)
        """
        if event_type:
            self._handlers[event_type].clear()
        else:
            self._handlers.clear()


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Get the global event bus instance.
    
    Returns:
        EventBus instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus