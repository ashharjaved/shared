"""
Message Repository Protocol
Defines persistence interfaces for inbound/outbound messages.
"""
from abc import abstractmethod
from typing import Optional, List, Protocol
from uuid import UUID
from datetime import datetime

from src.messaging.domain.entities.inbound_message import InboundMessage
from src.messaging.domain.entities.outbound_message import OutboundMessage


class InboundMessageRepository(Protocol):
    """Repository protocol for InboundMessage."""
    
    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Optional[InboundMessage]:
        """Retrieve inbound message by ID."""
        ...
    
    @abstractmethod
    async def get_by_wa_message_id(self, wa_message_id: str) -> Optional[InboundMessage]:
        """Find message by WhatsApp message ID (idempotency)."""
        ...
    
    @abstractmethod
    async def create(self, message: InboundMessage) -> InboundMessage:
        """Persist new inbound message."""
        ...
    
    @abstractmethod
    async def list_by_channel(
        self, channel_id: UUID, limit: int = 100
    ) -> List[InboundMessage]:
        """List recent inbound messages for a channel."""
        ...


class OutboundMessageRepository(Protocol):
    """Repository protocol for OutboundMessage."""
    
    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Optional[OutboundMessage]:
        """Retrieve outbound message by ID."""
        ...
    
    @abstractmethod
    async def create(self, message: OutboundMessage) -> OutboundMessage:
        """Persist new outbound message."""
        ...
    
    @abstractmethod
    async def update(self, message: OutboundMessage) -> OutboundMessage:
        """Update outbound message status."""
        ...
    
    @abstractmethod
    async def list_queued(
        self, channel_id: UUID, limit: int = 100
    ) -> List[OutboundMessage]:
        """List queued messages for a channel."""
        ...