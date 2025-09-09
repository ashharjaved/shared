from typing import List, Optional
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from messaging.domain.entities import WhatsAppChannel
from messaging.domain.repositories.channel_repo import WhatsAppChannelRepository
from messaging.infrastructure.encryption import get_encryption_service
from messaging.infrastructure.model.channelModel import WhatsAppChannelModel

class SQLAWhatsAppChannelRepository(WhatsAppChannelRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
        self.encryption = get_encryption_service()
    
    def _to_entity(self, model: WhatsAppChannelModel) -> WhatsAppChannel:
        # Decrypt credentials
        decrypted_credentials = {}
        if model.credentials:
            try:
                decrypted_credentials = {
                    k: self.encryption.decrypt(v) if isinstance(v, str) else v
                    for k, v in model.credentials.items()
                }
            except Exception as e:
                logger.error(f"Failed to decrypt credentials: {e}")
        
        return WhatsAppChannel(
            id=model.id,
            tenant_id=model.tenant_id,
            phone_number_id=model.phone_number_id,
            waba_id=model.waba_id,
            display_name=model.display_name,
            status=WhatsAppChannelStatus(model.status),
            credentials=decrypted_credentials,
            created_at=model.created_at
        )
    
    def _to_model(self, entity: WhatsAppChannel) -> WhatsAppChannelModel:
        # Encrypt credentials
        encrypted_credentials = {}
        if entity.credentials:
            encrypted_credentials = {
                k: self.encryption.encrypt(str(v)) if v is not None else None
                for k, v in entity.credentials.items()
            }
        
        return WhatsAppChannelModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            phone_number_id=entity.phone_number_id,
            waba_id=entity.waba_id,
            display_name=entity.display_name,
            status=entity.status.value,
            credentials=encrypted_credentials,
            created_at=entity.created_at
        )
    
    async def get_by_id(self, channel_id: UUID) -> Optional[WhatsAppChannel]:
        result = await self.session.execute(
            select(WhatsAppChannelModel).where(WhatsAppChannelModel.id == channel_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def get_by_tenant(self, tenant_id: UUID) -> List[WhatsAppChannel]:
        result = await self.session.execute(
            select(WhatsAppChannelModel).where(WhatsAppChannelModel.tenant_id == tenant_id)
        )
        return [self._to_entity(model) for model in result.scalars().all()]
    
    async def get_by_verify_token(self, verify_token: str) -> Optional[WhatsAppChannel]:
        # This is a bit complex since we need to decrypt and check each channel's verify_token
        result = await self.session.execute(select(WhatsAppChannelModel))
        for model in result.scalars().all():
            try:
                entity = self._to_entity(model)
                if entity.credentials.get('verify_token') == verify_token:
                    return entity
            except Exception:
                continue
        return None
    
    async def save(self, channel: WhatsAppChannel) -> None:
        model = self._to_model(channel)
        self.session.add(model)
        await self.session.flush()
    
    async def delete(self, channel_id: UUID) -> None:
        await self.session.execute(
            delete(WhatsAppChannelModel).where(WhatsAppChannelModel.id == channel_id)
        )

