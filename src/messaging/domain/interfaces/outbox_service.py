"""
Outbox service protocol for transactional event publishing.
"""
from typing import Protocol, Any
from uuid import UUID


class OutboxService(Protocol):
    """Protocol for outbox pattern implementation."""
    
    async def emit_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: UUID,
        idempotency_key: str | None = None
    ) -> None:
        """
        Emit an event to the outbox for async processing.
        
        Args:
            aggregate_type: Type of aggregate (e.g., "Message", "Channel")
            aggregate_id: ID of the aggregate
            event_type: Type of event (e.g., "MessageQueued", "MessageSent")
            payload: Event payload as JSON-serializable dict
            tenant_id: Tenant ID for isolation
            idempotency_key: Optional key to prevent duplicate events
        """
        ...