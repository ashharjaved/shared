# src/messaging/domain/repositories.py
from abc import ABC, abstractmethod
from typing import Optional, List
from ..entities import Message
from ..value_objects import WhatsAppMessageStatus, WhatsAppMessageId
from uuid import UUID


class WhatsAppMessageRepository(ABC):
    @abstractmethod
    async def get_by_id(self, tenant_id: UUID, message_id: int) -> Optional[Message]: ...
    @abstractmethod
    async def get_by_wa_message_id(self, tenant_id: UUID, wa_message_id: WhatsAppMessageId) -> Optional[Message]: ...
    @abstractmethod
    async def save(self, tenant_id: UUID, message: Message) -> Message: ...
    @abstractmethod
    async def update_status(self, tenant_id: UUID, message_id: int, status: WhatsAppMessageStatus, error_code: Optional[str] = None) -> None: ...
    @abstractmethod
    async def get_messages_by_status(self, tenant_id: UUID, status: WhatsAppMessageStatus, channel_id: Optional[UUID] = None, limit: int = 100, offset: int = 0) -> List[WhatsAppMessage]: ...
