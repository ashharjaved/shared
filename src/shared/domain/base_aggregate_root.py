"""
Aggregate Root Base Class
Manages domain events and acts as consistency boundary
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.domain.base_entity import BaseEntity
from shared.domain.domain_event import DomainEvent


class BaseAggregateRoot(BaseEntity):
    """
    Base class for aggregate roots.

    Aggregate roots are entities that serve as the entry point to an aggregate.
    They maintain a list of domain events that occurred during operations.
    These events are collected and published by infrastructure after persistence.

    Attributes:
        _domain_events: List of unpublished domain events
    """

    def __init__(self, id: UUID | None = None, **kwargs: Any) -> None:
        """
        Initialize aggregate root.

        Args:
            id: Aggregate UUID
            **kwargs: Additional arguments for BaseEntity
        """
        super().__init__(id=id, **kwargs)
        self._domain_events: list[DomainEvent] = []

    def add_domain_event(self, event: DomainEvent) -> None:
        """
        Add a domain event to the aggregate's event list.

        Args:
            event: Domain event to add
        """
        self._domain_events.append(event)

    def collect_domain_events(self) -> list[DomainEvent]:
        """
        Collect and clear domain events.

        This should be called by infrastructure after persistence
        to publish events via event bus.

        Returns:
            List of domain events that occurred
        """
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

    def clear_domain_events(self) -> None:
        """Clear all domain events without returning them."""
        self._domain_events.clear()

    def raise_event(self, event: DomainEvent) -> None:
        """Record a domain event, enriching it with aggregate context."""
        if event.aggregate_id is None:
            object.__setattr__(event, "aggregate_id", self.id)
        if not event.aggregate_type:
            object.__setattr__(event, "aggregate_type", self.__class__.__name__)
        self.add_domain_event(event)

    @property
    def has_domain_events(self) -> bool:
        """Check if aggregate has unpublished events."""
        return len(self._domain_events) > 0
