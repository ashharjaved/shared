# src/messaging/domain/events/channel_events.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

from ..types import ChannelId, TenantId, Timestamp

@dataclass(frozen=True, slots=True)
class ChannelEvent:
    """Base for channel events."""
    channel_id: ChannelId
    tenant_id: TenantId
    occurred_at: Timestamp = field(default_factory=datetime.utcnow)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at.isoformat(),
        }

@dataclass(frozen=True, slots=True)
class ChannelCreated(ChannelEvent):
    pass

@dataclass(frozen=True, slots=True)
class ChannelActivated(ChannelEvent):
    pass

@dataclass(frozen=True, slots=True)
class ChannelDeactivated(ChannelEvent):
    pass

@dataclass(frozen=True, slots=True)
class ChannelSecretsRotated(ChannelEvent):
    pass