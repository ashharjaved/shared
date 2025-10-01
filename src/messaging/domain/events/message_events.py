"""Domain events for messaging."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


@dataclass
class DomainEvent:
    """Base domain event."""
    event_id: UUID
    aggregate_id: UUID
    tenant_id: UUID
    event_type: str = field(init=False)
    occurred_at: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MessageReceived(DomainEvent):
    """Event when message is received via webhook."""
    channel_id: Optional[UUID] = None
    from_number: Optional[str] = None
    message_type: Optional[str] = None
    content: Optional[str] = None
    whatsapp_message_id: Optional[str] = None
    
    def __post_init__(self):
        if self.channel_id is None or self.from_number is None or self.message_type is None:
            raise ValueError("channel_id, from_number, and message_type are required")
        self.event_type = "message.received"


@dataclass
class MessageSent(DomainEvent):
    """Event when message is sent successfully."""
    channel_id: Optional[UUID] = None
    to_number: Optional[str] = None
    message_type: Optional[str] = None
    whatsapp_message_id: Optional[str] = None
    
    def __post_init__(self):
        if self.channel_id is None or self.to_number is None or self.message_type is None or self.whatsapp_message_id is None:
            raise ValueError("channel_id, to_number, message_type, and whatsapp_message_id are required")
        self.event_type = "message.sent"


@dataclass
class MessageRead(DomainEvent):
    """Event when message is read."""
    whatsapp_message_id: Optional[str] = None
    read_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.whatsapp_message_id is None or self.read_at is None:
            raise ValueError("whatsapp_message_id and read_at are required")
        self.event_type = "message.read"


@dataclass
class MessageDelivered(DomainEvent):
    """Event when message is delivered."""
    whatsapp_message_id: Optional[str] = None
    delivered_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.whatsapp_message_id is None or self.delivered_at is None:
            raise ValueError("whatsapp_message_id and delivered_at are required")
        self.event_type = "message.delivered"


@dataclass
class MessageFailed(DomainEvent):
    """Event when message fails to send."""
    channel_id: Optional[UUID] = None
    to_number: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    
    def __post_init__(self):
        if self.channel_id is None or self.to_number is None or self.error_code is None or self.error_message is None or self.retry_count is None:
            raise ValueError("channel_id, to_number, error_code, error_message, and retry_count are required")
        self.event_type = "message.failed"


@dataclass
class ChannelActivated(DomainEvent):
    """Event when channel is activated."""
    channel_name: Optional[str] = None
    phone_number: Optional[str] = None
    
    def __post_init__(self):
        if self.channel_name is None or self.phone_number is None:
            raise ValueError("channel_name and phone_number are required")
        self.event_type = "channel.activated"


@dataclass
class TemplateApproved(DomainEvent):
    """Event when template is approved."""
    template_name: Optional[str] = None
    whatsapp_template_id: Optional[str] = None
    
    def __post_init__(self):
        if self.template_name is None or self.whatsapp_template_id is None:
            raise ValueError("template_name and whatsapp_template_id are required")
        self.event_type = "template.approved"