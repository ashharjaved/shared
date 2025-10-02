"""
Inbound Message Entity
Represents messages received from WhatsApp users.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from shared.domain.base_entity import BaseEntity


class InboundMessage(BaseEntity):
    """
    Entity for inbound WhatsApp messages.
    
    Attributes:
        tenant_id: Owning tenant
        channel_id: Source channel
        wa_message_id: WhatsApp message ID (idempotency key)
        from_number: Sender phone (E.164)
        to_number: Recipient phone (channel number)
        message_type: text, voice, button, list_reply, etc.
        content: Message payload (JSON)
        timestamp_wa: WhatsApp message timestamp
        raw_payload: Full webhook payload
        processed: Processing status
    """
    
    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        channel_id: UUID,
        wa_message_id: str,
        from_number: str,
        to_number: str,
        message_type: str,
        content: dict,
        timestamp_wa: datetime,
        raw_payload: dict,
        processed: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        super().__init__(id, created_at, updated_at)
        self.tenant_id = tenant_id
        self.channel_id = channel_id
        self.wa_message_id = wa_message_id
        self.from_number = from_number
        self.to_number = to_number
        self.message_type = message_type
        self.content = content
        self.timestamp_wa = timestamp_wa
        self.raw_payload = raw_payload
        self.processed = processed
    
    def mark_processed(self) -> None:
        """Mark message as processed by conversation engine."""
        self.processed = True
    
    def __repr__(self) -> str:
        return f"<InboundMessage(id={self.id}, type={self.message_type}, from={self.from_number})>"