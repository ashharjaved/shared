"""Webhook DTOs."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, List, Optional
from datetime import datetime


class WebhookVerificationRequest(BaseModel):
    """Webhook verification challenge."""
    model_config = ConfigDict(extra="allow")
    
    hub_mode: str = Field(alias="hub.mode")
    hub_verify_token: str = Field(alias="hub.verify_token")
    hub_challenge: str = Field(alias="hub.challenge")


class WebhookPayload(BaseModel):
    """WhatsApp webhook payload."""
    model_config = ConfigDict(extra="allow")
    
    object: str
    entry: List[Dict[str, Any]]


class WebhookMessageData(BaseModel):
    """Parsed webhook message data."""
    model_config = ConfigDict(extra="forbid")
    
    message_id: str
    from_number: str
    timestamp: datetime
    type: str
    text: Optional[str] = None
    media_id: Optional[str] = None
    media_url: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class WebhookStatusData(BaseModel):
    """Parsed webhook status data."""
    model_config = ConfigDict(extra="forbid")
    
    message_id: str
    recipient_id: str
    status: str
    timestamp: datetime
    error: Optional[Dict[str, Any]] = None