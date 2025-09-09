# src/messaging/domain/events/quota_events.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any
from src.identity.domain.value_objects import Timestamps
from ..types import TenantId, ChannelId

@dataclass(frozen=True, slots=True)
class QuotaEvent:
    """Base for quota and rate limit events."""
    tenant_id: TenantId
    occurred_at: Timestamps = field(default_factory=datetime.utcnow)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at.update_timestamp(),
        }

@dataclass(frozen=True, slots=True)
class TenantQuotaExceeded(QuotaEvent):
    used: int
    limit: int

@dataclass(frozen=True, slots=True)
class ChannelRateLimited(QuotaEvent):
    channel_id: ChannelId