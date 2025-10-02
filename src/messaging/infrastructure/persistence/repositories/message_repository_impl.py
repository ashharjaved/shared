# =============================================================================
# FILE: src/modules/whatsapp/infrastructure/persistence/repositories/message_repository_impl.py
# =============================================================================
"""
SQLAlchemy Implementation of Message Repository
Maps between Message domain entities and MessageModel ORMs
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from messaging.infrastructure.persistence.models.inboundmessage_model import InboundMessageModel
from messaging.infrastructure.persistence.models.outboundmessage_model import OutboundMessageModel
from shared.infrastructure.database import SQLAlchemyRepository
from shared.infrastructure.observability import get_logger

from src.messaging.domain.entities.message import InboundMessage, OutboundMessage
from src.messaging.domain.value_objects.message_content import MessageContent
from src.messaging.domain.value_objects.message_status import (
    MessageDirection,
    MessageStatus,
    MessageType,
)
from src.messaging.domain.value_objects.phone_number import PhoneNumber
# from src.messaging.infrastructure.persistence.models import (
#     InboundMessageModel,
#     OutboundMessageModel,
# )

logger = get_logger(__name__)


class SQLAlchemyMessageRepository(SQLAlchemyRepository[InboundMessage, InboundMessageModel]):
    """
    SQLAlchemy implementation of MessageRepository.
    
    Handles both inbound and outbound messages with separate model mappings.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with session.
        
        Args:
            session: Async SQLAlchemy session with RLS context set
        """
        # Initialize with InboundMessage as default
        super().__init__(
            session=session,
            model_class=InboundMessageModel,
            entity_class=InboundMessage
        )
    
    # ==================== INBOUND MESSAGE METHODS ====================
    
    def _to_entity(self, model: InboundMessageModel) -> InboundMessage:
        """
        Convert InboundMessageModel to InboundMessage entity.
        
        Args:
            model: InboundMessageModel from database
            
        Returns:
            InboundMessage domain entity
        """
        return InboundMessage(
            id=model.id,
            account_id=model.account_id,
            wa_message_id=model.wa_message_id,
            from_phone=(model.from_phone),
            to_phone=(model.to_phone),
            message_type=MessageType(model.message_type),
            content=MessageContent(model.content),
            timestamp=model.timestamp,
            context=model.context,
            status=model.status,
            processed_at=model.processed_at,
            error_message=model.error_message,
            created_at=model.created_at,
        )
    
    def _to_model(self, entity: InboundMessage) -> InboundMessageModel:
        """
        Convert InboundMessage entity to InboundMessageModel.
        
        Args:
            entity: InboundMessage domain entity
            
        Returns:
            InboundMessageModel for database persistence
        """
        model = InboundMessageModel(
            id=entity.id,
            account_id=entity.account_id,
            wa_message_id=entity.wa_message_id,
            from_phone=entity.from_phone,
            to_phone=entity.to_phone,
            message_type=entity.message_type.value,
            content=entity.content.data,
            timestamp=entity.timestamp,
            context=entity.context,
            status=entity.status,
            processed_at=entity.processed_at,
            error_message=entity.error_message,
        )
        
        if hasattr(entity, 'created_at') and entity.created_at:
            model.created_at = entity.created_at
        
        return model
    
    async def save_inbound(self, message: InboundMessage) -> InboundMessage:
        """
        Save inbound message.
        
        Args:
            message: InboundMessage entity to save
            
        Returns:
            Saved InboundMessage entity
        """
        return await self.add(message)
    
    async def get_inbound_by_wa_id(
        self,
        wa_message_id: str
    ) -> Optional[InboundMessage]:
        """
        Get inbound message by WhatsApp message ID.
        
        Args:
            wa_message_id: WhatsApp message ID
            
        Returns:
            InboundMessage if found, None otherwise
        """
        try:
            stmt = select(InboundMessageModel).where(
                InboundMessageModel.wa_message_id == wa_message_id
            )
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model is None:
                return None
            
            return self._to_entity(model)
        
        except Exception as e:
            logger.error(
                "Failed to get inbound message by wa_id",
                extra={"error": str(e), "wa_message_id": wa_message_id}
            )
            raise
    
    # ==================== OUTBOUND MESSAGE METHODS ====================
    
    def _outbound_to_entity(self, model: OutboundMessageModel) -> OutboundMessage:
        """
        Convert OutboundMessageModel to OutboundMessage entity.
        
        Args:
            model: OutboundMessageModel from database
            
        Returns:
            OutboundMessage domain entity
        """
        return OutboundMessage(
            id=model.id,
            account_id=model.account_id,
            to_phone=(model.to_phone),
            message_type=MessageType(model.message_type),
            content=MessageContent(model.content),
            template_name=model.template_name,
            template_language=model.template_language,
            # template_params=model.template_params,
            template_params=cast(List[Dict[Any, Any]] | None, model.template_params),
            wa_message_id=model.wa_message_id,
            status=MessageStatus(model.status),
            sent_at=model.sent_at,
            delivered_at=model.delivered_at,
            read_at=model.read_at,
            failed_at=model.failed_at,
            error_code=model.error_code,
            error_message=model.error_message,
            retry_count=model.retry_count,
            idempotency_key=model.idempotency_key,
            metadata=model.metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _outbound_to_model(self, entity: OutboundMessage) -> OutboundMessageModel:
        """
        Convert OutboundMessage entity to OutboundMessageModel.
        
        Args:
            entity: OutboundMessage domain entity
            
        Returns:
            OutboundMessageModel for database persistence
        """
        model = OutboundMessageModel(
            id=entity.id,
            account_id=entity.account_id,
            to_phone=entity.to_phone,
            message_type=entity.message_type.value,
            content=entity.content.data,
            template_name=entity.template_name,
            template_language=entity.template_language,
            template_params=entity.template_params,
            wa_message_id=entity.wa_message_id,
            status=entity.status.value,
            sent_at=entity.sent_at,
            delivered_at=entity.delivered_at,
            read_at=entity.read_at,
            failed_at=entity.failed_at,
            error_code=entity.error_code,
            error_message=entity.error_message,
            retry_count=entity.retry_count,
            idempotency_key=entity.idempotency_key,
            metadata=entity.metadata,
        )
        
        if hasattr(entity, 'created_at') and entity.created_at:
            model.created_at = entity.created_at
        if hasattr(entity, 'updated_at') and entity.updated_at:
            model.updated_at = entity.updated_at
        
        return model
    
    async def save_outbound(self, message: OutboundMessage) -> OutboundMessage:
        """
        Save outbound message.
        
        Args:
            message: OutboundMessage entity to save
            
        Returns:
            Saved OutboundMessage entity
        """
        try:
            model = self._outbound_to_model(message)
            self.session.add(model)
            await self.session.flush()
            await self.session.refresh(model)
            
            logger.debug(
                "Saved outbound message",
                extra={
                    "message_id": str(message.id),
                    "to_phone": message.to_phone,
                    "idempotency_key": message.idempotency_key
                }
            )
            
            return self._outbound_to_entity(model)
        
        except Exception as e:
            logger.error(
                "Failed to save outbound message",
                extra={"error": str(e), "message_id": str(message.id)}
            )
            raise
    
    async def get_outbound_by_id(
        self,
        message_id: UUID
    ) -> Optional[OutboundMessage]:
        """
        Get outbound message by ID.
        
        Args:
            message_id: Message UUID
            
        Returns:
            OutboundMessage if found, None otherwise
        """
        try:
            stmt = select(OutboundMessageModel).where(
                OutboundMessageModel.id == message_id
            )
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model is None:
                return None
            
            return self._outbound_to_entity(model)
        
        except Exception as e:
            logger.error(
                "Failed to get outbound message by id",
                extra={"error": str(e), "message_id": str(message_id)}
            )
            raise
    
    async def get_outbound_by_wa_id(
        self,
        wa_message_id: str
    ) -> Optional[OutboundMessage]:
        """
        Get outbound message by WhatsApp message ID.
        
        Args:
            wa_message_id: WhatsApp message ID
            
        Returns:
            OutboundMessage if found, None otherwise
        """
        try:
            stmt = select(OutboundMessageModel).where(
                OutboundMessageModel.wa_message_id == wa_message_id
            )
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model is None:
                return None
            
            return self._outbound_to_entity(model)
        
        except Exception as e:
            logger.error(
                "Failed to get outbound message by wa_id",
                extra={"error": str(e), "wa_message_id": wa_message_id}
            )
            raise
    
    async def get_outbound_by_idempotency_key(
        self,
        key: str
    ) -> Optional[OutboundMessage]:
        """
        Get outbound message by idempotency key.
        
        Critical for preventing duplicate message sends.
        
        Args:
            key: Idempotency key (usually hash of content + recipient + timestamp)
            
        Returns:
            OutboundMessage if found, None otherwise
        """
        try:
            stmt = select(OutboundMessageModel).where(
                OutboundMessageModel.idempotency_key == key
            )
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model is not None:
                logger.debug(
                    "Found existing message by idempotency key",
                    extra={"idempotency_key": key, "message_id": str(model.id)}
                )
            
            return self._outbound_to_entity(model) if model else None
        
        except Exception as e:
            logger.error(
                "Failed to get outbound message by idempotency_key",
                extra={"error": str(e), "idempotency_key": key}
            )
            raise
    
    async def update_outbound(self, message: OutboundMessage) -> OutboundMessage:
        """
        Update outbound message (typically status updates).
        
        Args:
            message: OutboundMessage entity with updated values
            
        Returns:
            Updated OutboundMessage entity
        """
        try:
            model = self._outbound_to_model(message)
            merged = await self.session.merge(model)
            await self.session.flush()
            await self.session.refresh(merged)
            
            logger.debug(
                "Updated outbound message",
                extra={
                    "message_id": str(message.id),
                    "status": message.status.value,
                    "retry_count": message.retry_count
                }
            )
            
            return self._outbound_to_entity(merged)
        
        except Exception as e:
            logger.error(
                "Failed to update outbound message",
                extra={"error": str(e), "message_id": str(message.id)}
            )
            raise
    
    async def get_failed_for_retry(self, limit: int = 100) -> List[OutboundMessage]:
        """
        Get failed messages eligible for retry.
        
        Retrieves messages with status='failed' and retry_count < max_retries.
        Uses exponential backoff to determine eligible messages.
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of OutboundMessage entities eligible for retry
        """
        try:
            # Get failed messages with retry count < 12 (WhatsApp API retry limit)
            stmt = (
                select(OutboundMessageModel)
                .where(
                    and_(
                        OutboundMessageModel.status == MessageStatus.FAILED.value,
                        OutboundMessageModel.retry_count < 12
                    )
                )
                .order_by(OutboundMessageModel.failed_at.asc())
                .limit(limit)
            )
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            messages = [self._outbound_to_entity(model) for model in models]
            
            logger.debug(
                f"Retrieved {len(messages)} failed messages for retry",
                extra={"limit": limit}
            )
            
            return messages
        
        except Exception as e:
            logger.error(
                "Failed to get failed messages for retry",
                extra={"error": str(e), "limit": limit}
            )
            raise
