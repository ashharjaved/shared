"""Message repository implementation."""

from typing import Optional, List, cast, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func
import logging

from src.messaging.domain.interfaces.repositories import MessageRepository
from src.messaging.domain.entities.message import Message, MessageDirection, MessageStatus, MessageType
from src.messaging.infrastructure.models.message_model import MessageModel

logger = logging.getLogger(__name__)


class MessageRepositoryImpl(MessageRepository):
    """Message repository implementation using SQLAlchemy."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, message: Message) -> Message:
        """Create a new message."""
        try:
            model = MessageModel(
                id=message.id,
                tenant_id=message.tenant_id,
                channel_id=message.channel_id,
                direction=message.direction,
                message_type=message.message_type,
                from_number=message.from_number,
                to_number=message.to_number,
                content=message.content,
                media_url=message.media_url,
                template_id=message.template_id,
                template_variables=message.template_variables,
                whatsapp_message_id=message.whatsapp_message_id,
                status=message.status,
                error_code=message.error_code,
                error_message=message.error_message,
                metadata=message.metadata,
                retry_count=message.retry_count,
                max_retries=message.max_retries,
                created_at=message.created_at,
                updated_at=message.updated_at,
                sent_at=message.sent_at,
                delivered_at=message.delivered_at,
                read_at=message.read_at
            )
            
            self.session.add(model)
            await self.session.flush()
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to create message: {e}")
            raise
    
    async def get_by_id(self, message_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Message]:
        """Get message by ID."""
        try:
            stmt = select(MessageModel).where(
                and_(
                    MessageModel.id == message_id,
                    MessageModel.tenant_id == tenant_id
                )
            )
            
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                return self._to_entity(model)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            raise
    
    async def get_by_whatsapp_id(self, whatsapp_id: str, tenant_id: uuid.UUID) -> Optional[Message]:
        """Get message by WhatsApp ID."""
        try:
            stmt = select(MessageModel).where(
                and_(
                    MessageModel.whatsapp_message_id == whatsapp_id,
                    MessageModel.tenant_id == tenant_id
                )
            )
            
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                return self._to_entity(model)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get message by WhatsApp ID: {e}")
            raise
    
    async def list_by_channel(
        self, 
        channel_id: uuid.UUID, 
        tenant_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """List messages for a channel."""
        try:
            stmt = select(MessageModel).where(
                and_(
                    MessageModel.channel_id == channel_id,
                    MessageModel.tenant_id == tenant_id
                )
            ).order_by(
                MessageModel.created_at.desc()
            ).limit(limit).offset(offset)
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            return [self._to_entity(model) for model in models]
            
        except Exception as e:
            logger.error(f"Failed to list messages: {e}")
            raise
    
    async def list_pending_outbound(self, tenant_id: uuid.UUID, limit: int = 10) -> List[Message]:
        """List pending outbound messages."""
        try:
            stmt = select(MessageModel).where(
                and_(
                    MessageModel.tenant_id == tenant_id,
                    MessageModel.direction == MessageDirection.OUTBOUND,
                    MessageModel.status.in_([MessageStatus.QUEUED, MessageStatus.FAILED])
                )
            ).order_by(
                MessageModel.created_at.asc()
            ).limit(limit)
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            # Filter messages that can be retried
            messages = []
            for model in models:
                message = self._to_entity(model)
                if message.status == MessageStatus.QUEUED or message.can_retry():
                    messages.append(message)
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to list pending messages: {e}")
            raise
    
    async def update(self, message: Message) -> Message:
        """Update message."""
        try:
            stmt = update(MessageModel).where(
                and_(
                    MessageModel.id == message.id,
                    MessageModel.tenant_id == message.tenant_id
                )
            ).values(
                status=message.status,
                whatsapp_message_id=message.whatsapp_message_id,
                error_code=message.error_code,
                error_message=message.error_message,
                retry_count=message.retry_count,
                updated_at=message.updated_at,
                sent_at=message.sent_at,
                delivered_at=message.delivered_at,
                read_at=message.read_at
            )
            
            await self.session.execute(stmt)
            await self.session.flush()
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to update message: {e}")
            raise
    
    async def get_last_inbound_time(self, phone_number: str, tenant_id: uuid.UUID) -> Optional[datetime]:
        """Get timestamp of last inbound message from a phone number."""
        try:
            stmt = select(func.max(MessageModel.created_at)).where(
                and_(
                    MessageModel.tenant_id == tenant_id,
                    MessageModel.from_number == phone_number,
                    MessageModel.direction == MessageDirection.INBOUND
                )
            )
            
            result = await self.session.execute(stmt)
            last_time = result.scalar()
            
            return last_time
            
        except Exception as e:
            logger.error(f"Failed to get last inbound time: {e}")
            raise
    
    def _to_entity(self, model: MessageModel) -> Message:
        """Convert ORM model to domain entity."""
        return Message(
            id=cast(uuid.UUID, model.id),
            tenant_id=cast(uuid.UUID, model.tenant_id),
            channel_id=cast(uuid.UUID, model.channel_id),
            direction=cast(MessageDirection, model.direction),
            message_type=cast(MessageType, model.message_type),
            from_number=cast(str, model.from_number),
            to_number=cast(str, model.to_number),
            content=cast(Optional[str], model.content),
            media_url=cast(Optional[str], model.media_url),
            template_id=cast(Optional[uuid.UUID], model.template_id),
            template_variables=cast(Optional[Dict[str, str]], model.template_variables),
            whatsapp_message_id=cast(Optional[str], model.whatsapp_message_id),
            status=cast(MessageStatus, model.status),
            error_code=cast(Optional[str], model.error_code),
            error_message=cast(Optional[str], model.error_message),
            metadata=cast(Optional[Dict[str, Any]], model.metadata),
            retry_count=cast(int, model.retry_count),
            max_retries=cast(int, model.max_retries),
            created_at=cast(Optional[datetime], model.created_at),
            updated_at=cast(Optional[datetime], model.updated_at),
            sent_at=cast(Optional[datetime], model.sent_at),
            delivered_at=cast(Optional[datetime], model.delivered_at),
            read_at=cast(Optional[datetime], model.read_at)
        )