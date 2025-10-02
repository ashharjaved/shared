"""
Outbound Message Entity
Represents messages to be sent to WhatsApp users.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from shared.domain.base_entity import BaseEntity


class OutboundMessage(BaseEntity):
    """
    Entity for outbound WhatsApp messages queued for delivery.
    
    Attributes:
        tenant_id: Owning tenant
        channel_id: Target channel
        to_number: Recipient phone (E.164)
        message_type: text, template, interactive, etc.
        content: Message payload (JSON)
        template_id: Reference to message template (if template message)
        status: queued, sent, delivered, read, failed
        wa_message_id: WhatsApp message ID (after send)
        error_code: Error code if failed
        error_message: Error description
        retry_count: Number of retry attempts
        scheduled_at: When to send (for campaigns)
        sent_at: Actual send timestamp
        delivered_at: Delivery confirmation timestamp
        read_at: Read receipt timestamp
    """
    
    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        channel_id: UUID,
        to_number: str,
        message_type: str,
        content: dict,
        template_id: Optional[UUID] = None,
        status: str = "queued",
        wa_message_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        scheduled_at: Optional[datetime] = None,
        sent_at: Optional[datetime] = None,
        delivered_at: Optional[datetime] = None,
        read_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        super().__init__(id, created_at, updated_at)
        self.tenant_id = tenant_id
        self.channel_id = channel_id
        self.to_number = to_number
        self.message_type = message_type
        self.content = content
        self.template_id = template_id
        self.status = status
        self.wa_message_id = wa_message_id
        self.error_code = error_code
        self.error_message = error_message
        self.retry_count = retry_count
        self.scheduled_at = scheduled_at
        self.sent_at = sent_at
        self.delivered_at = delivered_at
        self.read_at = read_at
    
    def mark_sent(self, wa_message_id: str) -> None:
        """Mark message as successfully sent."""
        self.status = "sent"
        self.wa_message_id = wa_message_id
        self.sent_at = datetime.utcnow()
    
    def mark_delivered(self) -> None:
        """Mark message as delivered."""
        self.status = "delivered"
        self.delivered_at = datetime.utcnow()
    
    def mark_read(self) -> None:
        """Mark message as read by recipient."""
        self.status = "read"
        self.read_at = datetime.utcnow()
    
    def mark_failed(self, error_code: str, error_message: str) -> None:
        """Mark message as failed with error details."""
        self.status = "failed"
        self.error_code = error_code
        self.error_message = error_message
    
    def increment_retry(self) -> None:
        """Increment retry counter."""
        self.retry_count += 1
    
    def can_retry(self, max_retries: int = 12) -> bool:
        """Check if message can be retried."""
        return self.retry_count < max_retries
    
    def __repr__(self) -> str:
        return f"<OutboundMessage(id={self.id}, to={self.to_number}, status={self.status})>"