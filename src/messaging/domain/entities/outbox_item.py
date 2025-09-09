# src/messaging/domain/entities/outbox_item.py
"""Outbox item entity for reliable message delivery."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from ..exceptions import ValidationError, InvariantViolation
from ..types import OutboxId, TenantId, ChannelId, DedupeKey


class OutboxKind(Enum):
    """Type of outbox item for different delivery mechanisms."""
    WA_MESSAGE = "wa_message"      # WhatsApp message to send
    CALLBACK = "callback"          # HTTP callback to external system  
    WEBHOOK = "webhook"            # Webhook notification


@dataclass(frozen=True, slots=True)
class OutboxItem:
    """
    Outbox item for reliable at-least-once delivery.
    
    Represents a queued operation (message send, callback, webhook)
    that must be processed reliably with retry semantics.
    
    Invariants:
    - attempt must not exceed max_attempts
    - payload must not be empty
    - available_at determines when item can be processed
    - dedupe_key prevents duplicate processing when present
    
    Example:
        item = OutboxItem(
            id=OutboxId(1),
            tenant_id=TenantId(uuid4()),
            channel_id=ChannelId(uuid4()),
            kind=OutboxKind.WA_MESSAGE,
            payload={"to": "+1234567890", "text": {"body": "Hello"}},
            dedupe_key=DedupeKey("msg_123"),
            available_at=datetime.utcnow(),
            attempt=0,
            max_attempts=12
        )
    """
    
    id: OutboxId
    tenant_id: TenantId
    channel_id: ChannelId
    kind: OutboxKind
    payload: Dict[str, Any]
    dedupe_key: Optional[DedupeKey]
    available_at: datetime
    attempt: int
    max_attempts: int
    
    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        if not self.payload:
            raise ValidationError("payload cannot be empty", "payload")
        
        if self.attempt < 0:
            raise ValidationError("attempt cannot be negative", "attempt")
        
        if self.max_attempts <= 0:
            raise ValidationError("max_attempts must be positive", "max_attempts")
        
        if self.attempt > self.max_attempts:
            raise InvariantViolation(f"attempt {self.attempt} exceeds max_attempts {self.max_attempts}")
    
    def increment_attempt(self) -> 'OutboxItem':
        """
        Increment retry attempt counter.
        
        Returns:
            New OutboxItem instance with incremented attempt
            
        Raises:
            InvariantViolation: If already at max attempts
        """
        if self.is_retry_exhausted():
            raise InvariantViolation(f"Cannot increment: already at max_attempts {self.max_attempts}")
        
        return self._replace(attempt=self.attempt + 1)
    
    def is_retry_exhausted(self) -> bool:
        """
        Check if retry attempts are exhausted.
        
        Returns:
            True if no more retries allowed
        """
        return self.attempt >= self.max_attempts
    
    def is_available_for_processing(self) -> bool:
        """
        Check if item is ready for processing.
        
        Returns:
            True if available_at has passed and retries not exhausted
        """
        return (
            datetime.utcnow() >= self.available_at and
            not self.is_retry_exhausted()
        )
    
    def with_delayed_retry(self, delay_seconds: int) -> 'OutboxItem':
        """
        Create new item with delayed availability for retry.
        
        Args:
            delay_seconds: Seconds to delay next processing attempt
            
        Returns:
            New OutboxItem with updated available_at
        """
        if delay_seconds < 0:
            raise ValidationError("delay_seconds cannot be negative", "delay_seconds")
        
        new_available_at = datetime.utcnow().replace(
            second=datetime.utcnow().second + delay_seconds
        )
        
        return self._replace(available_at=new_available_at)
    
    def _replace(self, **changes) -> 'OutboxItem':
        """Create new instance with specified changes."""
        from dataclasses import replace
        return replace(self, **changes)