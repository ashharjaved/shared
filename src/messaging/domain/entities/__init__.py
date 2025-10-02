# src/modules/whatsapp/domain/entities/__init__.py
"""
WhatsApp Domain Entities
"""
from .channel import Channel
from .message import InboundMessage,OutboundMessage

__all__ = [
    "InboundMessage",
    "OutboundMessage",
    "Channel"
]