from __future__ import annotations
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class TriggerRequest(BaseModel):
    tenant_id: UUID
    channel_id: UUID
    contact_id: str = Field(min_length=3)
    payload: Dict[str, Any] = Field(default_factory=dict)
    event_id: Optional[str] = None  # for idempotency (e.g., inbound message id)

class OutboundPreview(BaseModel):
    message_type: str
    to_phone: str
    content: Dict[str, Any]

class SessionRead(BaseModel):
    session_id: UUID
    state: str
    vars: Dict[str, Any]
    updated_at: str

class FlowRead(BaseModel):
    id: UUID
    name: str
    version: int
    start_node_id: str
