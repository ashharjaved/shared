# src/messaging/domain/entities/message.py
"""Message aggregate root."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..exceptions import ValidationError, InvalidStateTransition
from ..types import MessageId, TenantId, ChannelId, WhatsAppMessageId, MSISDN
from ..value_objects import Direction, MessageStatus, Payload


@dataclass(slots=True)
class Message:
    """Message aggregate root.
    
    Represents a WhatsApp message (inbound or outbound) with
    status tracking and validation rules.
    """
    
    id: MessageId
    tenant_id: TenantId
    channel_id: ChannelId
    wa_message_id: Optional[WhatsAppMessageId]
    direction: Direction
    from_msisdn: MSISDN
    to_msisdn: MSISDN
    payload: Payload
    status: MessageStatus
    error_code: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def __post_init__(self) -> None:
        """Validate message invariants on construction.
        
        Raises:
            ValidationError: If message data violates invariants
            
        Examples:
            >>> from uuid import uuid4
            >>> from datetime import datetime
            >>> msg = Message(
            ...     id=MessageId(1),
            ...     tenant_id=TenantId(uuid4()),
            ...     channel_id=ChannelId(uuid4()),
            ...     wa_message_id=WhatsAppMessageId("wamid.123"),
            ...     direction=Direction.IN,
            ...     from_msisdn=MSISDN("+1234567890"),
            ...     to_msisdn=MSISDN("+0987654321"),
            ...     payload=Payload({"text": "Hello"}),
            ...     status=MessageStatus.QUEUED,
            ...     error_code=None,
            ...     created_at=datetime.now()
            ... )
            >>> msg.is_inbound()
            True
        """
        self._validate_msisdn_format()
        self._validate_inbound_invariants()
        self._validate_status_error_consistency()
    
    @classmethod
    def create_inbound(cls, tenant_id: TenantId, channel_id: ChannelId, wa_message_id: WhatsAppMessageId, from_msisdn: MSISDN, to_msisdn: MSISDN, payload: Payload) -> tuple["Message", MessageReceived]:
        msg = cls(
            id=MessageId(0),  # Assigned by DB
            tenant_id=tenant_id,
            channel_id=channel_id,
            wa_message_id=wa_message_id,
            direction=DirectionVO(Direction.IN),
            from_msisdn=from_msisdn,
            to_msisdn=to_msisdn,
            payload=payload,
            status=MessageStatusVO(MessageStatus.DELIVERED),  # Inbound starts as delivered
        )
        event = MessageReceived(message_id=msg.id, tenant_id=msg.tenant_id, occurred_at=msg.created_at)
        return msg, event

    def _validate_msisdn_format(self) -> None:
        """Validate MSISDN format."""
        for msisdn, field in [(self.from_msisdn, "from_msisdn"), 
                             (self.to_msisdn, "to_msisdn")]:
            if not msisdn:
                raise ValidationError(f"{field} cannot be empty")
            if not msisdn.startswith('+'):
                raise ValidationError(f"{field} must start with '+'")
            if len(msisdn) < 8 or len(msisdn) > 15:
                raise ValidationError(f"{field} must be 8-15 characters")
    
    def _validate_inbound_invariants(self) -> None:
        """Validate inbound message invariants."""
        if self.direction.is_inbound() and not self.wa_message_id:
            raise ValidationError("Inbound messages must have wa_message_id")

    def mark_sent(self, wa_message_id: Optional[WhatsAppMessageId] = None) -> 'Message':
        """
        Mark message as sent to WhatsApp API.
        
        Args:
            wa_message_id: WhatsApp-assigned message ID (for outbound)
            
        Returns:
            New Message instance with SENT status
            
        Raises:
            InvalidMessageTransition: If current status doesn't allow sent
        """
        _validate_transition(MessageStatus.SENT)
        
        updates = {"status": MessageStatus.SENT}
        if wa_message_id and self.direction == Direction.OUTBOUND:
            updates["wa_message_id"] = wa_message_id
            
        return self._replace(**updates)

    def mark_delivered(self) -> 'Message':
        """
        Mark message as delivered to recipient.
        
        Returns:
            New Message instance with DELIVERED status
            
        Raises:
            InvalidMessageTransition: If current status doesn't allow delivered
        """
        self._validate_transition(MessageStatus.DELIVERED)
        return self._replace(status=MessageStatus.DELIVERED)

    def mark_read(self) -> 'Message':
        """
        Mark message as read by recipient.
        
        Returns:
            New Message instance with READ status
            
        Raises:
            InvalidMessageTransition: If current status doesn't allow read
        """
        self._validate_transition(MessageStatus.READ)
        return self._replace(status=MessageStatus.READ)

    def mark_failed(self, error_code: ErrorCode) -> 'Message':
        """
        Mark message as failed with error code.
        
        Args:
            error_code: WhatsApp error code or internal error
            
        Returns:
            New Message instance with FAILED status
            
        Raises:
            ValidationError: If error_code is empty
        """
        if not error_code:
            raise ValidationError("error_code required when marking failed", "error_code")
        
        return self._replace(status=MessageStatus.FAILED, error_code=error_code)
    
    def is_inbound(self) -> bool:
        """Check if message is inbound from user."""
        return self.direction == Direction.INBOUND
    
    def is_outbound(self) -> bool:
        """Check if message is outbound to user."""
        return self.direction == Direction.OUTBOUND
    
    def _is_valid_msisdn(self, msisdn: MSISDN) -> bool:
        """Basic E.164 format validation."""
        return (
            isinstance(msisdn, str) and
            msisdn.startswith('+') and
            len(msisdn) >= 8 and
            len(msisdn) <= 15 and
            msisdn[1:].isdigit()
        )
    
    def _replace(self, **changes) -> 'Message':
        """Create new instance with specified changes."""
        from dataclasses import replace
        return replace(self, **changes)