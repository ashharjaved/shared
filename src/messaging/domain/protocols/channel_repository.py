from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID

from messaging.domain.entities.channel import Channel


class ChannelRepository(ABC):
    """Repository interface for Channel aggregate."""
    
    @abstractmethod
    async def get_by_id(self, channel_id: UUID) -> Optional[Channel]:
        """Get channel by ID."""
        pass
    
    @abstractmethod
    async def get_by_phone_number_id(self, phone_number_id: str) -> Optional[Channel]:
        """Get channel by WhatsApp phone number ID."""
        pass
    
    @abstractmethod
    async def get_by_organization(self, organization_id: UUID) -> List[Channel]:
        """Get all channels for an organization."""
        pass
    
    @abstractmethod
    async def save(self, channel: Channel) -> Channel:
        """Save channel."""
        pass
    
    @abstractmethod
    async def update(self, channel: Channel) -> Channel:
        """Update channel."""
        pass