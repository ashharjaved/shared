"""Repository interfaces for messaging domain."""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
import uuid

from ..entities.channel import Channel
from ..entities.message import Message
from ..entities.template import MessageTemplate


class ChannelRepository(ABC):
    """Repository interface for Channel entity."""
    
    @abstractmethod
    async def create(self, channel: Channel) -> Channel:
        """Create a new channel."""
        pass
    
    @abstractmethod
    async def get_by_id(self, channel_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Channel]:
        """Get channel by ID."""
        pass
    
    @abstractmethod
    async def get_by_phone_number(self, phone_number: str, tenant_id: uuid.UUID) -> Optional[Channel]:
        """Get channel by phone number."""
        pass
    
    @abstractmethod
    async def list_by_tenant(self, tenant_id: uuid.UUID) -> List[Channel]:
        """List all channels for a tenant."""
        pass
    
    @abstractmethod
    async def update(self, channel: Channel) -> Channel:
        """Update channel."""
        pass
    
    @abstractmethod
    async def delete(self, channel_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Delete channel (soft delete)."""
        pass


class MessageRepository(ABC):
    """Repository interface for Message entity."""
    
    @abstractmethod
    async def create(self, message: Message) -> Message:
        """Create a new message."""
        pass
    
    @abstractmethod
    async def get_by_id(self, message_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Message]:
        """Get message by ID."""
        pass
    
    @abstractmethod
    async def get_by_whatsapp_id(self, whatsapp_id: str, tenant_id: uuid.UUID) -> Optional[Message]:
        """Get message by WhatsApp ID."""
        pass
    
    @abstractmethod
    async def list_by_channel(
        self, 
        channel_id: uuid.UUID, 
        tenant_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """List messages for a channel."""
        pass
    
    @abstractmethod
    async def list_pending_outbound(self, tenant_id: uuid.UUID, limit: int = 10) -> List[Message]:
        """List pending outbound messages."""
        pass
    
    @abstractmethod
    async def update(self, message: Message) -> Message:
        """Update message."""
        pass
    
    @abstractmethod
    async def get_last_inbound_time(self, phone_number: str, tenant_id: uuid.UUID) -> Optional[datetime]:
        """Get timestamp of last inbound message from a phone number."""
        pass


class TemplateRepository(ABC):
    """Repository interface for MessageTemplate entity."""
    
    @abstractmethod
    async def create(self, template: MessageTemplate) -> MessageTemplate:
        """Create a new template."""
        pass
    
    @abstractmethod
    async def get_by_id(self, template_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[MessageTemplate]:
        """Get template by ID."""
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str, channel_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[MessageTemplate]:
        """Get template by name."""
        pass
    
    @abstractmethod
    async def list_by_channel(
        self,
        channel_id: uuid.UUID,
        tenant_id: uuid.UUID,
        status_filter: Optional[str] = None
    ) -> List[MessageTemplate]:
        """List templates for a channel."""
        pass
    
    @abstractmethod
    async def update(self, template: MessageTemplate) -> MessageTemplate:
        """Update template."""
        pass
    
    @abstractmethod
    async def delete(self, template_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Delete template."""
        pass