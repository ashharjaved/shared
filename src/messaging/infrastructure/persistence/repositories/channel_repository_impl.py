# src/messaging/infrastructure/persistence/repositories/channel_repository_impl.py
"""
SQLAlchemy Implementation of ChannelRepository
Extends generic SQLAlchemyRepository base class
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.domain.entities.channel import Channel
from src.messaging.domain.protocols.channel_repository import ChannelRepository
from src.messaging.infrastructure.persistence.models.channel_model import ChannelModel
from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from shared.infrastructure.database.rls import RLSManager
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class ChannelRepositoryImpl(SQLAlchemyRepository[Channel, ChannelModel], ChannelRepository):
    """
    SQLAlchemy implementation of ChannelRepository.
    
    Inherits CRUD operations from SQLAlchemyRepository and implements
    domain-specific channel queries with RLS enforcement.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        """
        Initialize channel repository with session and tenant context.
        
        Args:
            session: Active async database session
            tenant_id: Tenant UUID for RLS enforcement
        """
        super().__init__(
            session=session,
            model_class=ChannelModel,
            entity_class=Channel
        )
        self.tenant_id = tenant_id
    
    # ========================================================================
    # DOMAIN-SPECIFIC QUERIES
    # ========================================================================
    
    async def get_by_tenant_and_phone(
        self, 
        tenant_id: UUID, 
        phone_number_id: str
    ) -> Optional[Channel]:
        """
        Find channel by tenant and phone number ID.
        
        Args:
            tenant_id: Organization UUID
            phone_number_id: WhatsApp phone number ID
            
        Returns:
            Channel entity if found, None otherwise
        """
        await RLSManager.set_tenant_context(self.session, tenant_id)
        
        try:
            stmt = select(ChannelModel).where(
                ChannelModel.tenant_id == tenant_id,
                ChannelModel.phone_number_id == phone_number_id
            )
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                logger.debug(
                    "Channel found by phone number",
                    extra={
                        "tenant_id": str(tenant_id),
                        "phone_number_id": phone_number_id,
                        "channel_id": str(model.id)
                    }
                )
            
            return self._to_entity(model) if model else None
            
        except Exception as e:
            logger.error(
                "Failed to get channel by phone number",
                extra={
                    "error": str(e),
                    "tenant_id": str(tenant_id),
                    "phone_number_id": phone_number_id
                }
            )
            raise
    
    async def list_by_tenant(self, tenant_id: UUID) -> List[Channel]:
        """
        List all channels for a tenant.
        
        Args:
            tenant_id: Organization UUID
            
        Returns:
            List of channel entities
        """
        await RLSManager.set_tenant_context(self.session, tenant_id)
        
        try:
            # Use inherited find_all with filters
            channels = await self.find_all(
                tenant_id=tenant_id,
                order_by="created_at"
            )
            
            logger.debug(
                "Listed channels for tenant",
                extra={
                    "tenant_id": str(tenant_id),
                    "count": len(channels)
                }
            )
            
            return list(channels)
            
        except Exception as e:
            logger.error(
                "Failed to list channels for tenant",
                extra={"error": str(e), "tenant_id": str(tenant_id)}
            )
            raise
    
    async def get_active_channels(self, tenant_id: UUID) -> List[Channel]:
        """
        Get all active channels for a tenant.
        
        Args:
            tenant_id: Organization UUID
            
        Returns:
            List of active channel entities
        """
        await RLSManager.set_tenant_context(self.session, tenant_id)
        
        try:
            # Use inherited find_all with status filter
            channels = await self.find_all(
                tenant_id=tenant_id,
                status="active",
                order_by="created_at"
            )
            
            logger.debug(
                "Listed active channels",
                extra={
                    "tenant_id": str(tenant_id),
                    "count": len(channels)
                }
            )
            
            return list(channels)
            
        except Exception as e:
            logger.error(
                "Failed to get active channels",
                extra={"error": str(e), "tenant_id": str(tenant_id)}
            )
            raise
    
    # ========================================================================
    # OVERRIDE METHODS WITH RLS ENFORCEMENT
    # ========================================================================
    
    async def get_by_id(self, channel_id: UUID) -> Optional[Channel]:
        """
        Retrieve channel by ID with RLS enforcement.
        
        Args:
            channel_id: Channel UUID
            
        Returns:
            Channel entity if found, None otherwise
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        return await super().get_by_id(channel_id)
    
    async def add(self, entity: Channel) -> Channel:
        """
        Add new channel with RLS enforcement.
        
        Args:
            entity: Channel entity to persist
            
        Returns:
            Persisted channel entity
        """
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().add(entity)
    
    async def update(self, entity: Channel) -> Channel:
        """
        Update channel with RLS enforcement.
        
        Args:
            entity: Channel entity with updated values
            
        Returns:
            Updated channel entity
        """
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().update(entity)
    
    async def delete(self, channel_id: UUID) -> bool:
        """
        Soft-delete channel by marking status as deleted.
        
        Args:
            channel_id: Channel UUID
            
        Returns:
            True if deleted, False if not found
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            # Find the channel first
            channel = await self.get_by_id(channel_id)
            if not channel:
                return False
            
            # Update status to deleted instead of hard delete
            channel.status = "deleted"
            await self.update(channel)
            
            logger.debug(
                "Channel soft-deleted",
                extra={
                    "channel_id": str(channel_id),
                    "tenant_id": str(self.tenant_id)
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete channel",
                extra={
                    "error": str(e),
                    "channel_id": str(channel_id)
                }
            )
            raise
    
    # ========================================================================
    # ENTITY <-> MODEL MAPPING
    # ========================================================================
    
    def _to_entity(self, model: ChannelModel) -> Channel:
        """
        Convert ORM model to domain entity.
        
        Args:
            model: ChannelModel ORM instance
            
        Returns:
            Channel domain entity
        """
        return Channel(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            phone_number_id=model.phone_number_id,
            business_phone=model.business_phone,
            waba_id=model.waba_id,
            access_token_encrypted=model.access_token_encrypted,
            status=model.status,
            rate_limit_per_second=model.rate_limit_per_second,
            monthly_message_limit=model.monthly_message_limit,
            webhook_verify_token=model.webhook_verify_token,
            metadata=model.metadata or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: Channel) -> ChannelModel:
        """
        Convert domain entity to ORM model.
        
        Args:
            entity: Channel domain entity
            
        Returns:
            ChannelModel ORM instance
        """
        return ChannelModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            phone_number_id=entity.phone_number_id,
            business_phone=entity.business_phone,
            waba_id=entity.waba_id,
            access_token_encrypted=entity.access_token_encrypted,
            status=entity.status,
            rate_limit_per_second=entity.rate_limit_per_second,
            monthly_message_limit=entity.monthly_message_limit,
            webhook_verify_token=entity.webhook_verify_token,
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )