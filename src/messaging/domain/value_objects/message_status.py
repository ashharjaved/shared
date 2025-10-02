# src/modules/whatsapp/domain/value_objects/message_status.py
"""
Message Status and Type Enums
"""
from enum import Enum


class MessageDirection(str, Enum):
    """Message flow direction."""
    INBOUND = "inbound"   # Received from user
    OUTBOUND = "outbound"  # Sent to user


class MessageType(str, Enum):
    """WhatsApp message types."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"  # Buttons, lists
    TEMPLATE = "template"  # Pre-approved template
    REACTION = "reaction"
    UNSUPPORTED = "unsupported"
    STICKER = "sticker"

class MessageStatus(str, Enum):
    """
    WhatsApp message delivery status.
    
    Flow: pending → sent → delivered → read
    Can fail at any stage → failed
    """
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
