# =============================================================================
# FILE: src/modules/whatsapp/infrastructure/persistence/repositories/channel_repository_impl.py
# =============================================================================
"""
SQLAlchemy Implementation of Channel Repository
Maps between Channel domain entity and ChannelModel ORM
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from messaging.domain.protocols.channel_repository import ChannelRepository
from messaging.infrastructure.persistence.models.whatsapp_account_model import WhatsAppAccountModel
from shared.infrastructure.database import SQLAlchemyRepository
from shared.infrastructure.observability import get_logger
from shared.infrastructure.security import get_encryption_manager

from src.messaging.domain.entities.channel import Channel
from src.messaging.domain.value_objects.message_content import (
    AccessToken,
    ChannelStatus,
    RateLimitTier,
    WhatsAppBusinessAccountId,
)
from src.messaging.domain.value_objects.phone_number import PhoneNumber
#from src.messaging.infrastructure.persistence.models. import ChannelModel

logger = get_logger(__name__)


class SQLAlchemyChannelRepository(SQLAlchemyRepository[Channel, WhatsAppAccountModel],ChannelRepository):
    """
    SQLAlchemy implementation of ChannelRepository.
    
    Handles:
    - Entity ↔ Model mapping
    - Encryption/decryption of access tokens
    - RLS enforcement (via session context)
    - Query optimization
    """
    
    def __init__(self, session: AsyncSession, encryption: FieldEncryption):
        super().__init__(session, WhatsAppAccountModel)
        self.encryption = encryption
    
    def _to_domain(self, model: WhatsAppAccountModel) -> Channel:
        """Convert ORM model to domain entity."""
        return Channel(
            id=model.id,
            organization_id=model.organization_id,
            phone_number=PhoneNumber(
                display_number=model.display_phone_number,
                phone_number_id=model.phone_number_id
            ),
            business_account_id=WhatsAppBusinessAccountId(model.business_account_id),
            access_token=AccessToken(
                self.encryption.decrypt(model.access_token_encrypted)
            ),
            webhook_verify_token=self.encryption.decrypt(
                model.webhook_verify_token_encrypted
            ),
            status=ChannelStatus(model.status),
            rate_limit_tier=RateLimitTier(model.rate_limit_tier),
            metadata=model.metadata or {},
            created_at=model.created_at,
            updated_at=model.updated_at
        )
    
    def _to_model(self, entity: Channel) -> WhatsAppAccountModel:
        """Convert domain entity to ORM model."""
        return WhatsAppAccountModel(
            id=entity.id,
            organization_id=entity.organization_id,
            phone_number_id=entity.phone_number.phone_number_id,
            display_phone_number=entity.phone_number.display_number,
            business_account_id=entity.business_account_id.value,
            access_token_encrypted=self.encryption.encrypt(entity.access_token.value),
            webhook_verify_token_encrypted=self.encryption.encrypt(entity.webhook_verify_token),
            status=entity.status.value,
            rate_limit_tier=entity.rate_limit_tier.value,
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
    
    async def get_by_phone_number_id(
        self,
        phone_number_id: str
    ) -> Optional[Channel]:
        """
        Get channel by WhatsApp phone number ID.
        
        Args:
            phone_number_id: WhatsApp Business API phone number ID
            
        Returns:
            Channel if found, None otherwise
        """
        try:
            stmt = select(WhatsAppAccountModel).where(
                WhatsAppAccountModel.phone_number_id == phone_number_id
            )
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model is None:
                logger.debug(
                    "Channel not found by phone_number_id",
                    extra={"phone_number_id": phone_number_id}
                )
                return None
            
            return self._to_entity(model)
        
        except Exception as e:
            logger.error(
                "Failed to get channel by phone_number_id",
                extra={"error": str(e), "phone_number_id": phone_number_id}
            )
            raise
    
    async def get_by_organization(
        self,
        organization_id: UUID
    ) -> List[Channel]:
        """
        Get all channels for an organization (tenant).
        
        Note: RLS automatically filters by tenant_id from session context.
        This method adds additional organization_id filter if needed.
        
        Args:
            organization_id: Organization/tenant UUID
            
        Returns:
            List of channels for the organization
        """
        try:
            stmt = (
                select(WhatsAppAccountModel)
                .where(WhatsAppAccountModel.organization_id == organization_id)
                .where(WhatsAppAccountModel.status != ChannelStatus.DELETED.value)
                .order_by(WhatsAppAccountModel.created_at.desc())
            )
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            channels = [self._to_entity(model) for model in models]
            
            logger.debug(
                f"Retrieved {len(channels)} channels for organization",
                extra={"organization_id": str(organization_id)}
            )
            
            return channels
        
        except Exception as e:
            logger.error(
                "Failed to get channels by organization",
                extra={"error": str(e), "organization_id": str(organization_id)}
            )
            raise
    
    async def get_active_channels(self) -> List[Channel]:
        """
        Get all active channels (for current tenant via RLS).
        
        Returns:
            List of active channels
        """
        try:
            stmt = (
                select(WhatsAppAccountModel)
                .where(WhatsAppAccountModel.status == ChannelStatus.ACTIVE.value)                
                .order_by(WhatsAppAccountModel.created_at.desc())
            )
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            return [self._to_entity(model) for model in models]
        
        except Exception as e:
            logger.error(
                "Failed to get active channels",
                extra={"error": str(e)}
            )
            raise