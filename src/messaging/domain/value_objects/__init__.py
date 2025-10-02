# src/modules/whatsapp/domain/value_objects/__init__.py
"""
WhatsApp Domain Value Objects

Immutable value objects representing WhatsApp-specific concepts.
"""
from .phone_number import PhoneNumber
from .message_content import MessageContent, ChannelStatus, RateLimitTier, WhatsAppBusinessAccountId, AccessToken
from .message_status import MessageStatus, MessageDirection, MessageType

__all__ = [
    "PhoneNumber",
    "MessageContent",
    "MessageStatus",
    "MessageDirection",
    "MessageType",
    "ChannelStatus",
    "RateLimitTier",
    "WhatsAppBusinessAccountId",
    "AccessToken"
]