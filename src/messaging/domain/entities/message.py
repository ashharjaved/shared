"""Message entity for WhatsApp messages."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from uuid import UUID

class MessageDirection(Enum):
    """Message direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(Enum):
    """Message delivery status."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    EXPIRED = "expired"


class MessageType(Enum):
    """WhatsApp message type."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    TEMPLATE = "template"
    INTERACTIVE = "interactive"


@dataclass
class Message:
    """WhatsApp message entity."""
    id: UUID
    tenant_id: UUID
    channel_id: UUID
    direction: MessageDirection
    message_type: MessageType
    from_number: str
    to_number: str
    content: Optional[str] = None
    media_url: Optional[str] = None
    template_id: Optional[UUID] = None
    template_variables: Optional[Dict[str, str]] = None
    whatsapp_message_id: Optional[str] = None  # WhatsApp's ID
    status: MessageStatus = MessageStatus.QUEUED
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 12
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamps."""
        now = datetime.utcnow()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return (
            self.direction == MessageDirection.OUTBOUND and
            self.status == MessageStatus.FAILED and
            self.retry_count < self.max_retries
        )
    
    def mark_sent(self, whatsapp_id: str) -> None:
        """Mark message as sent."""
        self.status = MessageStatus.SENT
        self.whatsapp_message_id = whatsapp_id
        self.sent_at = datetime.utcnow()
        self.updated_at = self.sent_at
    
    def mark_delivered(self) -> None:
        """Mark message as delivered."""
        self.status = MessageStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
        self.updated_at = self.delivered_at
    
    def mark_read(self) -> None:
        """Mark message as read."""
        self.status = MessageStatus.READ
        self.read_at = datetime.utcnow()
        self.updated_at = self.read_at
    
    def mark_failed(self, error_code: str, error_message: str) -> None:
        """Mark message as failed."""
        self.status = MessageStatus.FAILED
        self.error_code = error_code
        self.error_message = error_message
        self.retry_count += 1
        self.updated_at = datetime.utcnow()
    
    def is_within_session_window(self, last_inbound: datetime) -> bool:
        """
        Check if message is within 24-hour session window.
        Session messages don't require templates.
        """
        if self.direction == MessageDirection.INBOUND:
            return True
        time_diff = datetime.utcnow() - last_inbound
        return time_diff.total_seconds() < 24 * 60 * 60  # 24 hours