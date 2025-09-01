from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ChannelCreate(BaseModel):
    name: str
    phone_number_id: str
    business_phone: str
    access_token: str = Field(..., min_length=10)
    is_active: bool = True
    rate_limit_per_second: Optional[int] = None
    monthly_message_limit: Optional[int] = None


class ChannelResponse(BaseModel):
    id: UUID
    name: str
    phone_number_id: str
    business_phone: str
    is_active: bool
    rate_limit_per_second: Optional[int] = None
    monthly_message_limit: Optional[int] = None


class MessageSendRequest(BaseModel):
    channel_id: UUID
    to: str
    content: Dict[str, Any]
    type: str = Field("text", pattern="^(text|template|media)$")
    idempotency_key: Optional[str] = None


class MessageResponse(BaseModel):
    id: UUID
    channel_id: UUID
    from_phone: str
    to_phone: str
    status: str
    created_at: Optional[datetime] = None
