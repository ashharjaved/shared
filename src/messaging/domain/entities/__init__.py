# src/modules/whatsapp/domain/entities/__init__.py
"""
WhatsApp Domain Entities
"""
from .channel import Channel
from .inbound_message import InboundMessage
from .outbound_message import OutboundMessage
from .message_template import MessageTemplate

__all__ = [
    "InboundMessage",
    "OutboundMessage",
    "Channel",
    "MessageTemplate"
]