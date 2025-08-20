from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

@dataclass
class TriggerFlow:
    tenant_id: UUID
    channel_id: UUID
    contact_id: str
    inbound_payload: Dict[str, Any]
    event_id: Optional[str] = None

@dataclass
class RunTick:
    tenant_id: UUID
    session_id: UUID
    inbound_payload: Dict[str, Any]
    event_id: Optional[str] = None
