"""
Channel Repository Protocol
Defines persistence interface for Channel aggregate.
"""
from abc import abstractmethod
from typing import Optional, List, Protocol
from uuid import UUID

from src.messaging.domain.entities.channel import Channel


class ChannelRepository(Protocol):
    """Repository protocol for Channel persistence."""
    
    @abstractmethod
    async def get_by_id(self, channel_id: UUID) -> Optional[Channel]:
        """Retrieve channel by ID."""
        ...
    
    @abstractmethod
    async def get_by_tenant_and_phone(
        self, tenant_id: UUID, phone_number_id: str
    ) -> Optional[Channel]:
        """Find channel by tenant and phone number ID."""
        ...
    
    @abstractmethod
    async def list_by_tenant(self, tenant_id: UUID) -> List[Channel]:
        """List all channels for a tenant."""
        ...
    
    @abstractmethod
    async def create(self, channel: Channel) -> Channel:
        """Persist new channel."""
        ...
    
    @abstractmethod
    async def update(self, channel: Channel) -> Channel:
        """Update existing channel."""
        ...
    
    @abstractmethod
    async def delete(self, channel_id: UUID) -> None:
        """Soft-delete channel."""
        ...