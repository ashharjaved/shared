from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from messaging.domain.repositories.message_repo import WhatsAppMessageRepository
from src.messaging.domain.entities import WhatsAppMessage
from src.messaging.domain.value_objects import WhatsAppMessageDirection, WhatsAppMessageStatus
from src.messaging.infrastructure.model.messagemodel import WhatsAppMessageModel


class SQLAWhatsAppMessageRepository(WhatsAppMessageRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    def _to_entity(self, model: WhatsAppMessageModel) -> WhatsAppMessage:
        return WhatsAppMessage(
            id=model.id,
            tenant_id=model.tenant_id,
            channel_id=model.channel_id,
            wa_message_id=model.wa_message_id,
            direction=WhatsAppMessageDirection(model.direction),
            from_msisdn=model.from_msisdn,
            to_msisdn=model.to_msisdn,
            payload=model.payload,
            template_name=model.template_name,
            status=WhatsAppMessageStatus(model.status),
            error_code=model.error_code,
            created_at=model.created_at
        )
    
    def _to_model(self, entity: WhatsAppMessage) -> WhatsAppMessageModel:
        return WhatsAppMessageModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            channel_id=entity.channel_id,
            wa_message_id=entity.wa_message_id,
            direction=entity.direction.value if entity.direction else None,
            from_msisdn=entity.from_msisdn,
            to_msisdn=entity.to_msisdn,
            payload=entity.payload,
            template_name=entity.template_name,
            status=entity.status.value if entity.status else None,
            error_code=entity.error_code,
            created_at=entity.created_at
        )
    
    async def get_by_id(self, message_id: int) -> Optional[WhatsAppMessage]:
        result = await self.session.execute(
            select(WhatsAppMessageModel).where(WhatsAppMessageModel.id == message_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def get_by_wa_message_id(self, wa_message_id: str) -> Optional[WhatsAppMessage]:
        result = await self.session.execute(
            select(WhatsAppMessageModel).where(WhatsAppMessageModel.wa_message_id == wa_message_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def save(self, message: WhatsAppMessage) -> WhatsAppMessage:
        model = self._to_model(message)
        self.session.add(model)
        await self.session.flush()
        # Refresh to get the generated ID
        await self.session.refresh(model)
        message.id = model.id
        return message
    
    async def update_status(self, message_id: int, status: WhatsAppMessageStatus, error_code: Optional[str] = None) -> None:
        await self.session.execute(
            update(WhatsAppMessageModel)
            .where(WhatsAppMessageModel.id == message_id)
            .values(status=status.value, error_code=error_code)
        )
    
    async def get_messages_by_status(self, status: WhatsAppMessageStatus, limit: int = 100) -> List[WhatsAppMessage]:
        result = await self.session.execute(
            select(WhatsAppMessageModel)
            .where(WhatsAppMessageModel.status == status.value)
            .limit(limit)
        )
        return [self._to_entity(model) for model in result.scalars().all()]
