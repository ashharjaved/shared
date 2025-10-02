# src/modules/whatsapp/domain/protocols/__init__.py
"""
WhatsApp Domain Protocols (Repository Interfaces)
"""
from .message_repository import InboundMessageRepository, OutboundMessageRepository
from .channel_repository import ChannelRepository
from .rate_limiter import RateLimiter
from .whatsapp_gateway_repository import WhatsAppGateway
from .speech_transcription import SpeechTranscription
from .template_repository import TemplateRepository

__all__ = [
    "ChannelRepository",
    "InboundMessageRepository",
    "WhatsAppGateway",
    "RateLimiter",
    "OutboundMessageRepository",
    "TemplateRepository",
    "SpeechTranscription"
]