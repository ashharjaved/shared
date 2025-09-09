# src/messaging/domain/events/outbox_events.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

from ..types import OutboxId, TenantId, Timestamp

@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Base for outbox events."""
    outbox_id: OutboxId
    tenant_id: TenantId
    occurred_at: Timestamp = field(default_factory=datetime.utcnow)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "outbox_id": self.outbox_id,
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at.isoformat(),
        }

@dataclass(frozen=True, slots=True)
class OutboxEnqueued(OutboxEvent):
    pass

@dataclass(frozen=True, slots=True)
class OutboxDispatched(OutboxEvent):
    pass

@dataclass(frozen=True, slots=True)
class OutboxExhausted(OutboxEvent):
    pass