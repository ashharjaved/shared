"""Channel repository implementation."""

from typing import Optional, List, cast
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete
import logging

from shared.database.rls import verify_rls_context
from shared.errors import RlsNotSetError
from src.messaging.domain.interfaces.repositories import ChannelRepository
from src.messaging.domain.entities.channel import Channel, ChannelStatus
from src.messaging.infrastructure.models.channel_model import ChannelModel
from src.messaging.infrastructure.adapters.encryption_adapter import EncryptionAdapter

logger = logging.getLogger(__name__)


class ChannelRepositoryImpl(ChannelRepository):
    """Channel repository implementation using SQLAlchemy."""
    
    def __init__(self, session: AsyncSession, encryption: EncryptionAdapter):
        self.session = session
        self.encryption = encryption
    
    async def create(self, channel: Channel) -> Channel:
        """Create a new channel."""
        try:
            # Encrypt sensitive data
            encrypted_token = self.encryption.encrypt(channel.access_token)
            
            model = ChannelModel(
                id=channel.id,
                tenant_id=channel.tenant_id,
                name=channel.name,
                phone_number_id=channel.phone_number_id,
                business_phone=channel.business_phone,
                access_token=encrypted_token,
                status=channel.status,
                rate_limit_per_second=channel.rate_limit_per_second,
                monthly_message_limit=channel.monthly_message_limit,
                current_month_usage=channel.current_month_usage,
                webhook_verify_token=channel.webhook_verify_token,
                created_at=channel.created_at,
                updated_at=channel.updated_at
            )
            
            self.session.add(model)
            await self.session.flush()
            
            return channel
            
        except Exception as e:
            logger.error(f"Failed to create channel: {e}")
            raise
    
    async def get_by_id(self, channel_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Channel]:
        """Get channel by ID."""
        try:
            stmt = select(ChannelModel).where(
                and_(
                    ChannelModel.id == channel_id,
                    ChannelModel.tenant_id == tenant_id,
                    ChannelModel.deleted_at.is_(None)
                )
            )
            
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                return self._to_entity(model)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get channel: {e}")
            raise
    
    async def get_by_phone_number(self, phone_number: str, tenant_id: uuid.UUID) -> Optional[Channel]:
        """Get channel by phone number."""
        try:
            stmt = select(ChannelModel).where(
                and_(
                    ChannelModel.business_phone == phone_number,
                    ChannelModel.tenant_id == tenant_id,
                    ChannelModel.deleted_at.is_(None)
                )
            )
            
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                return self._to_entity(model)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get channel by phone: {e}")
            raise
    
    async def list_by_tenant(self, tenant_id: uuid.UUID) -> List[Channel]:
        """List all channels for a tenant."""
        try:
            stmt = select(ChannelModel).where(
                and_(
                    ChannelModel.tenant_id == tenant_id,
                    ChannelModel.deleted_at.is_(None)
                )
            ).order_by(ChannelModel.created_at.desc())
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            return [self._to_entity(model) for model in models]
            
        except Exception as e:
            logger.error(f"Failed to list channels: {e}")
            raise
    
    async def update(self, channel: Channel) -> Channel:
        """Update channel."""
        try:
            # Encrypt token if changed
            encrypted_token = self.encryption.encrypt(channel.access_token)
            
            stmt = update(ChannelModel).where(
                and_(
                    ChannelModel.id == channel.id,
                    ChannelModel.tenant_id == channel.tenant_id
                )
            ).values(
                name=channel.name,
                access_token=encrypted_token,
                status=channel.status,
                rate_limit_per_second=channel.rate_limit_per_second,
                monthly_message_limit=channel.monthly_message_limit,
                current_month_usage=channel.current_month_usage,
                updated_at=channel.updated_at
            )
            
            await self.session.execute(stmt)
            await self.session.flush()
            
            return channel
            
        except Exception as e:
            logger.error(f"Failed to update channel: {e}")
            raise
    
    async def delete(self, channel_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Soft delete channel."""
        try:
            stmt = update(ChannelModel).where(
                and_(
                    ChannelModel.id == channel_id,
                    ChannelModel.tenant_id == tenant_id
                )
            ).values(
                deleted_at=datetime.utcnow(),
                status=ChannelStatus.INACTIVE
            )
            
            await self.session.execute(stmt)
            await self.session.flush()
            
        except Exception as e:
            logger.error(f"Failed to delete channel: {e}")
            raise
    
    async def increment_usage(
        self,
        channel_id: uuid.UUID,
        tenant_id: uuid.UUID,
        count: int = 1
    ) -> None:
        """Increment monthly usage counter with RLS enforcement."""
        try:
            # ✅ ENFORCE RLS
            await verify_rls_context(self.session)
            
            stmt = (
                update(ChannelModel)
                .where(
                    and_(
                        ChannelModel.id == channel_id,
                        ChannelModel.tenant_id == tenant_id
                    )
                )
                .values(
                    current_month_usage=ChannelModel.current_month_usage + count,
                    updated_at=datetime.utcnow()
                )
            )
            
            await self.session.execute(stmt)
            
        except RlsNotSetError:
            logger.error("RLS context not set")
            raise
        except Exception as e:
            logger.error("Failed to increment usage")
            raise

    def _to_entity(self, model: ChannelModel) -> Channel:
        """Convert ORM model to domain entity."""
        # Decrypt sensitive data
        decrypted_token = self.encryption.decrypt(cast(str, model.access_token))
        
        return Channel(
            id=cast(uuid.UUID, model.id),
            tenant_id=cast(uuid.UUID, model.tenant_id),
            name=cast(str, model.name),
            phone_number_id=cast(str, model.phone_number_id),
            business_phone=cast(str, model.business_phone),
            access_token=decrypted_token,
            status=cast(ChannelStatus, model.status),
            rate_limit_per_second=cast(int, model.rate_limit_per_second),
            monthly_message_limit=cast(Optional[int], model.monthly_message_limit),
            current_month_usage=cast(int, model.current_month_usage),
            webhook_verify_token=cast(Optional[str], model.webhook_verify_token),
            created_at=cast(Optional[datetime], model.created_at),
            updated_at=cast(Optional[datetime], model.updated_at)
        )