from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional
from uuid import UUID, uuid4
from ..types import *
from ..value_objects import Timestamps
from dataclasses import is_dataclass, asdict

def _serialize(value: Any) -> Any:
    """PII-safe, JSON-friendly serializer for events."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        # Always ISO 8601 with timezone
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):  # Ensure it's an instance, not a type
        return {k: _serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class EventBase:
    """
    Standard envelope for all domain events.
    - Immutable & slotted
    - UTC timestamp
    - Correlation/causation for tracing across services
    - Metadata for non-PII addenda (never secrets)
    """
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=Timestamps._utcnow)

    # Every event is tenant-scoped in this platform
    tenant_id: TenantId =TenantId(uuid4())

    # Optional tracing
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None

    # Free-form, non-PII metadata (e.g., {"source":"api.v1"})
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly dict; UUIDs & datetimes serialized safely."""
        return _serialize(self)  # type: ignore
