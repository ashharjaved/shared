"""Base domain event."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class DomainEvent:
    """Base class for all domain events."""
    
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID | None = None
    tenant_id: UUID | None = None
    
    def to_dict(self) -> dict:
        """Convert event to dictionary."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.__class__.__name__,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
        }