"""
Domain Event Base Class
All domain events inherit from this
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events.
    
    Domain events represent something that happened in the domain.
    They are immutable and carry all necessary data.
    
    Attributes:
        event_id: Unique identifier for this event occurrence
        occurred_at: Timestamp when event occurred
        aggregate_id: ID of the aggregate that produced this event
        aggregate_type: Type name of the aggregate
        event_version: Schema version of this event type (for evolution)
    """
    
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID | None = None
    aggregate_type: str = ""
    event_version: int = 1
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation of event
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.__class__.__name__,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "aggregate_type": self.aggregate_type,
            "event_version": self.event_version,
        }