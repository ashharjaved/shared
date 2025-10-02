# src/modules/whatsapp/domain/protocols/__init__.py
"""
WhatsApp Domain Protocols (Repository Interfaces)
"""
from .message_repository import MessageRepository
from .channel_repository import ChannelRepository
from .rate_limiter import RateLimiter
from .whatsapp_gateway_repository import WhatsAppGateway

__all__ = [
    "ChannelRepository",
    "MessageRepository",
    "WhatsAppGateway",
    "RateLimiter"
]