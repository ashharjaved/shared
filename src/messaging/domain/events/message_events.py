# src/messaging/domain/events/message_events.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

from ..types import MessageId, TenantId, Timestamp

@dataclass(frozen=True, slots=True)
class MessageEvent:
    """Base for message events."""
    message_id: MessageId
    tenant_id: TenantId
    occurred_at: Timestamp = field(default_factory=datetime.utcnow)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at.isoformat(),
        }

@dataclass(frozen=True, slots=True)
class MessageReceived(MessageEvent):
    pass

@dataclass(frozen=True, slots=True)
class MessageQueued(MessageEvent):
    pass

@dataclass(frozen=True, slots=True)
class MessageSent(MessageEvent):
    pass

@dataclass(frozen=True, slots=True)
class MessageDelivered(MessageEvent):
    pass

@dataclass(frozen=True, slots=True)
class MessageRead(MessageEvent):
    pass

@dataclass(frozen=True, slots=True)
class MessageFailed(MessageEvent):
    error_code: str