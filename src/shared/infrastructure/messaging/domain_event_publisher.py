"""
Domain Event Publisher
Collects events from aggregates and persists to outbox
"""
from __future__ import annotations

from typing import Any

from shared.domain.base_aggregate_root import BaseAggregateRoot
from shared.domain.domain_event import DomainEvent
from shared.infrastructure.messaging.outbox_pattern import OutboxEvent
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class DomainEventPublisher:
    """
    Publishes domain events to the outbox for reliable delivery.
    
    Collects events from aggregate roots after persistence and
    writes them to the outbox table within the same transaction.
    """
    
    @staticmethod
    async def publish_events_from_aggregate(
        aggregate: BaseAggregateRoot,
        session: Any,  # AsyncSession
    ) -> None:
        """
        Collect and publish events from an aggregate.
        
        Should be called after aggregate is persisted, within same transaction.
        
        Args:
            aggregate: Aggregate root with domain events
            session: Async database session
        """
        events = aggregate.collect_domain_events()
        
        if not events:
            return
        
        logger.info(
            f"Publishing {len(events)} events from aggregate",
            extra={
                "aggregate_id": str(aggregate.id),
                "aggregate_type": aggregate.__class__.__name__,
                "event_count": len(events),
            },
        )
        
        for event in events:
            await DomainEventPublisher._persist_to_outbox(event, session)
    
    @staticmethod
    async def _persist_to_outbox(event: DomainEvent, session: Any) -> None:
        """
        Persist a domain event to the outbox table.
        
        Args:
            event: Domain event to persist
            session: Async database session
        """
        outbox_event = OutboxEvent(
            id=event.event_id,
            aggregate_id=event.aggregate_id,
            aggregate_type=event.aggregate_type,
            event_type=event.__class__.__name__,
            event_data=event.to_dict(),
            occurred_at=event.occurred_at,
        )
        
        session.add(outbox_event)
        
        logger.debug(
            f"Event persisted to outbox: {event.__class__.__name__}",
            extra={"event_id": str(event.event_id)},
        )