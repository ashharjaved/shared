# src/messaging/domain/entities/__init__.py
"""Domain entities for messaging module."""

from .channel import Channel
from .message import Message
from .outbox_item import OutboxItem

__all__ = [
    'Channel',
    'Message',
    'OutboxItem',
]
