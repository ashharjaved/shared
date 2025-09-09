from abc import ABC, abstractmethod
# channel_repo.py
from uuid import UUID
from typing import List, Optional
from messaging.domain.entities import WhatsAppChannel

class WhatsAppChannelRepository(ABC):
    @abstractmethod
    async def get_by_id(self, tenant_id: UUID, channel_id: UUID) -> Optional[WhatsAppChannel]: ...
    @abstractmethod
    async def get_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[WhatsAppChannel]: ...
    @abstractmethod
    async def get_by_phone_number_id(self, tenant_id: UUID, phone_number_id: str) -> Optional[WhatsAppChannel]: ...
    @abstractmethod
    async def save(self, tenant_id: UUID, channel: WhatsAppChannel) -> WhatsAppChannel: ...
    @abstractmethod
    async def delete(self, tenant_id: UUID, channel_id: UUID) -> None: ...
