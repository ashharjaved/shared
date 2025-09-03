from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ChannelCreate(BaseModel):
    phone_number_id: str
    business_phone: str
    access_token: str = Field(..., min_length=10)
    webhook_url: str
    is_active: bool = True
    rate_limit_per_second: Optional[int] = None
    monthly_message_limit: Optional[int] = None


class ChannelResponse(BaseModel):
    id: UUID
    name: str
    phone_number_id: str
    business_phone: str
    is_active: bool
    webhook_url: str
    rate_limit_per_second: Optional[int] = None
    monthly_message_limit: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


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
