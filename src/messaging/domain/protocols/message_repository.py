from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from messaging.domain.entities.message import InboundMessage, OutboundMessage


class MessageRepository(ABC):
    """Repository interface for messages."""
    
    @abstractmethod
    async def save_inbound(self, message: InboundMessage) -> InboundMessage:
        """Save inbound message."""
        pass
    
    @abstractmethod
    async def save_outbound(self, message: OutboundMessage) -> OutboundMessage:
        """Save outbound message."""
        pass
    
    @abstractmethod
    async def get_inbound_by_wa_id(self, wa_message_id: str) -> Optional[InboundMessage]:
        """Get inbound message by WhatsApp ID."""
        pass
    
    @abstractmethod
    async def get_outbound_by_id(self, message_id: UUID) -> Optional[OutboundMessage]:
        """Get outbound message by ID."""
        pass
    
    @abstractmethod
    async def get_outbound_by_wa_id(self, wa_message_id: str) -> Optional[OutboundMessage]:
        """Get outbound message by WhatsApp ID."""
        pass
    
    @abstractmethod
    async def get_outbound_by_idempotency_key(self, key: str) -> Optional[OutboundMessage]:
        """Get outbound message by idempotency key."""
        pass
    
    @abstractmethod
    async def update_outbound(self, message: OutboundMessage) -> OutboundMessage:
        """Update outbound message."""
        pass
    
    @abstractmethod
    async def get_failed_for_retry(self, limit: int = 100) -> List[OutboundMessage]:
        """Get failed messages eligible for retry."""
        pass