"""Domain events for WhatsApp module."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from shared.domain.domain_event import DomainEvent


class ChannelProvisionedEvent(DomainEvent):
    """Event raised when a new channel is provisioned."""
    
    def __init__(
        self,
        channel_id: UUID,
        organization_id: UUID,
        phone_number: str
    ):
        super().__init__()
        self.channel_id = channel_id
        self.organization_id = organization_id
        self.phone_number = phone_number


class ChannelSuspendedEvent(DomainEvent):
    """Event raised when a channel is suspended."""
    
    def __init__(self, channel_id: UUID, reason: str):
        super().__init__()
        self.channel_id = channel_id
        self.reason = reason


class ChannelActivatedEvent(DomainEvent):
    """Event raised when a channel is activated."""
    
    def __init__(self, channel_id: UUID):
        super().__init__()
        self.channel_id = channel_id


class MessageReceivedEvent(DomainEvent):
    """Event raised when an inbound message is received."""
    
    def __init__(
        self,
        message_id: UUID,
        channel_id: UUID,
        from_phone: str,
        message_type: str,
        content: Dict[str, Any]
    ):
        super().__init__()
        self.message_id = message_id
        self.channel_id = channel_id
        self.from_phone = from_phone
        self.message_type = message_type
        self.content = content


class MessageSentEvent(DomainEvent):
    """Event raised when a message is sent successfully."""
    
    def __init__(
        self,
        message_id: UUID,
        channel_id: UUID,
        to_phone: str,
        wa_message_id: str
    ):
        super().__init__()
        self.message_id = message_id
        self.channel_id = channel_id
        self.to_phone = to_phone
        self.wa_message_id = wa_message_id


class MessageDeliveredEvent(DomainEvent):
    """Event raised when a message is delivered."""
    
    def __init__(
        self,
        message_id: UUID,
        wa_message_id: str,
        timestamp: datetime
    ):
        super().__init__()
        self.message_id = message_id
        self.wa_message_id = wa_message_id
        self.timestamp = timestamp


class MessageFailedEvent(DomainEvent):
    """Event raised when message delivery fails."""
    
    def __init__(
        self,
        message_id: UUID,
        error_code: str,
        error_message: str
    ):
        super().__init__()
        self.message_id = message_id
        self.error_code = error_code
        self.error_message = error_message