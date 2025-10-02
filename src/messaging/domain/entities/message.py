"""Message entities for inbound and outbound messages."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum

from shared.domain.base_entity import BaseEntity
from src.messaging.domain.value_objects import (
    MessageType,
    MessageStatus,
    MessageContent
)


class InboundMessage(BaseEntity):
    """Inbound WhatsApp message."""

    def __init__(
        self,
        id: UUID,
        account_id: UUID,
        wa_message_id: str,
        from_phone: str,
        to_phone: str,
        message_type: MessageType,
        content: MessageContent,
        timestamp: datetime,
        context: Optional[Dict[str, Any]] = None,
        status: str = "received",
        processed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        super().__init__(id)
        self.account_id = account_id
        self.wa_message_id = wa_message_id
        self.from_phone = from_phone
        self.to_phone = to_phone
        self.message_type = message_type
        self.content = content
        self.timestamp = timestamp
        self.context = context or {}
        self.status = status
        self.processed_at = processed_at
        self.error_message = error_message
        self.created_at = created_at or datetime.utcnow()

    def mark_processed(self) -> None:
        """Mark message as processed."""
        self.status = "processed"
        self.processed_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        """Mark message as failed."""
        self.status = "failed"
        self.error_message = error
        self.processed_at = datetime.utcnow()


class OutboundMessage(BaseEntity):
    """Outbound WhatsApp message."""

    def __init__(
        self,
        id: UUID,
        account_id: UUID,
        to_phone: str,
        message_type: MessageType,
        content: MessageContent,
        template_name: Optional[str] = None,
        template_language: Optional[str] = None,
        template_params: Optional[List[Dict]] = None,
        wa_message_id: Optional[str] = None,
        status: MessageStatus = MessageStatus.QUEUED,
        sent_at: Optional[datetime] = None,
        delivered_at: Optional[datetime] = None,
        read_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        super().__init__(id)
        self.account_id = account_id
        self.to_phone = to_phone
        self.message_type = message_type
        self.content = content
        self.template_name = template_name
        self.template_language = template_language
        self.template_params = template_params
        self.wa_message_id = wa_message_id
        self.status = status
        self.sent_at = sent_at
        self.delivered_at = delivered_at
        self.read_at = read_at
        self.failed_at = failed_at
        self.error_code = error_code
        self.error_message = error_message
        self.retry_count = retry_count
        self.idempotency_key = idempotency_key
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def mark_sent(self, wa_message_id: str) -> None:
        """Mark message as sent."""
        self.wa_message_id = wa_message_id
        self.status = MessageStatus.SENT
        self.sent_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_delivered(self) -> None:
        """Mark message as delivered."""
        self.status = MessageStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_read(self) -> None:
        """Mark message as read."""
        self.status = MessageStatus.READ
        self.read_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error_code: str, error_message: str) -> None:
        """Mark message as failed."""
        self.status = MessageStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.error_code = error_code
        self.error_message = error_message
        self.updated_at = datetime.utcnow()

    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.updated_at = datetime.utcnow()

    def should_retry(self, max_retries: int = 12) -> bool:
        """Check if message should be retried."""
        return (
            self.status == MessageStatus.FAILED
            and self.retry_count < max_retries
            and self.error_code not in ["131051", "131052"]  # Permanent errors
        )