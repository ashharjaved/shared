# src/messaging/infrastructure/persistence/repositories/message_repository_impl.py
"""
SQLAlchemy Implementation of Message Repositories
Extends generic SQLAlchemyRepository base class
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.domain.entities.inbound_message import InboundMessage
from src.messaging.domain.entities.outbound_message import OutboundMessage
from src.messaging.domain.protocols.message_repository import (
    InboundMessageRepository,
    OutboundMessageRepository,
)
from src.messaging.infrastructure.persistence.models.inboundmessage_model import InboundMessageModel
from src.messaging.infrastructure.persistence.models.outboundmessage_model import OutboundMessageModel
from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from shared.infrastructure.database.rls import RLSManager
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class InboundMessageRepositoryImpl(
    SQLAlchemyRepository[InboundMessage, InboundMessageModel], 
    InboundMessageRepository
):
    """
    SQLAlchemy implementation of InboundMessageRepository.
    
    Inherits CRUD operations from SQLAlchemyRepository and implements
    domain-specific inbound message queries with RLS enforcement.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        """
        Initialize inbound message repository.
        
        Args:
            session: Active async database session
            tenant_id: Tenant UUID for RLS enforcement
        """
        super().__init__(
            session=session,
            model_class=InboundMessageModel,
            entity_class=InboundMessage
        )
        self.tenant_id = tenant_id
    
    # ========================================================================
    # DOMAIN-SPECIFIC QUERIES
    # ========================================================================
    
    async def get_by_wa_message_id(self, wa_message_id: str) -> Optional[InboundMessage]:
        """
        Find message by WhatsApp message ID (idempotency check).
        
        Args:
            wa_message_id: WhatsApp's unique message identifier
            
        Returns:
            InboundMessage if found, None otherwise
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            # Use inherited find_one with wa_message_id filter
            message = await self.find_one(
                tenant_id=self.tenant_id,
                wa_message_id=wa_message_id
            )
            
            if message:
                logger.debug(
                    "Inbound message found by WA message ID",
                    extra={
                        "wa_message_id": wa_message_id,
                        "message_id": str(message.id)
                    }
                )
            
            return message
            
        except Exception as e:
            logger.error(
                "Failed to get inbound message by WA message ID",
                extra={"error": str(e), "wa_message_id": wa_message_id}
            )
            raise
    
    async def list_by_channel(
        self, 
        channel_id: UUID, 
        limit: int = 100
    ) -> List[InboundMessage]:
        """
        List recent inbound messages for a channel.
        
        Args:
            channel_id: Channel UUID
            limit: Maximum number of messages to return
            
        Returns:
            List of inbound messages ordered by creation time (newest first)
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            messages = await self.find_all(
                tenant_id=self.tenant_id,
                channel_id=channel_id,
                limit=limit,
                order_by="created_at"
            )
            
            # Reverse to get newest first (SQLAlchemy orders asc by default)
            result = list(reversed(list(messages)))
            
            logger.debug(
                "Listed inbound messages for channel",
                extra={
                    "channel_id": str(channel_id),
                    "count": len(result)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to list inbound messages",
                extra={"error": str(e), "channel_id": str(channel_id)}
            )
            raise
    
    async def list_unprocessed(
        self, 
        channel_id: UUID, 
        limit: int = 100
    ) -> List[InboundMessage]:
        """
        List unprocessed inbound messages for a channel.
        
        Args:
            channel_id: Channel UUID
            limit: Maximum number of messages to return
            
        Returns:
            List of unprocessed inbound messages
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            messages = await self.find_all(
                tenant_id=self.tenant_id,
                channel_id=channel_id,
                processed=False,
                limit=limit,
                order_by="created_at"
            )
            
            logger.debug(
                "Listed unprocessed inbound messages",
                extra={
                    "channel_id": str(channel_id),
                    "count": len(messages)
                }
            )
            
            return list(messages)
            
        except Exception as e:
            logger.error(
                "Failed to list unprocessed messages",
                extra={"error": str(e), "channel_id": str(channel_id)}
            )
            raise
    
    # ========================================================================
    # OVERRIDE METHODS WITH RLS ENFORCEMENT
    # ========================================================================
    
    async def get_by_id(self, message_id: UUID) -> Optional[InboundMessage]:
        """Retrieve inbound message by ID with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        return await super().get_by_id(message_id)
    
    async def add(self, entity: InboundMessage) -> InboundMessage:
        """Add new inbound message with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().add(entity)
    
    async def update(self, entity: InboundMessage) -> InboundMessage:
        """Update inbound message with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().update(entity)
    
    # ========================================================================
    # ENTITY <-> MODEL MAPPING
    # ========================================================================
    
    def _to_entity(self, model: InboundMessageModel) -> InboundMessage:
        """Convert ORM model to domain entity."""
        return InboundMessage(
            id=model.id,
            tenant_id=model.tenant_id,
            channel_id=model.channel_id,
            wa_message_id=model.wa_message_id,
            from_number=model.from_number,
            to_number=model.to_number,
            message_type=model.message_type,
            content=model.content,
            timestamp_wa=model.timestamp_wa,
            raw_payload=model.raw_payload or {},
            processed=model.processed,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: InboundMessage) -> InboundMessageModel:
        """Convert domain entity to ORM model."""
        return InboundMessageModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            channel_id=entity.channel_id,
            wa_message_id=entity.wa_message_id,
            from_number=entity.from_number,
            to_number=entity.to_number,
            message_type=entity.message_type,
            content=entity.content,
            timestamp_wa=entity.timestamp_wa,
            raw_payload=entity.raw_payload,
            processed=entity.processed,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class OutboundMessageRepositoryImpl(
    SQLAlchemyRepository[OutboundMessage, OutboundMessageModel], 
    OutboundMessageRepository
):
    """
    SQLAlchemy implementation of OutboundMessageRepository.
    
    Inherits CRUD operations from SQLAlchemyRepository and implements
    domain-specific outbound message queries with RLS enforcement.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        """
        Initialize outbound message repository.
        
        Args:
            session: Active async database session
            tenant_id: Tenant UUID for RLS enforcement
        """
        super().__init__(
            session=session,
            model_class=OutboundMessageModel,
            entity_class=OutboundMessage
        )
        self.tenant_id = tenant_id
    
    # ========================================================================
    # DOMAIN-SPECIFIC QUERIES
    # ========================================================================
    
    async def list_queued(
        self, 
        channel_id: UUID, 
        limit: int = 100
    ) -> List[OutboundMessage]:
        """
        List queued messages for a channel.
        
        Args:
            channel_id: Channel UUID
            limit: Maximum number of messages to return
            
        Returns:
            List of queued outbound messages ordered by creation time (oldest first)
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            messages = await self.find_all(
                tenant_id=self.tenant_id,
                channel_id=channel_id,
                status="queued",
                limit=limit,
                order_by="created_at"
            )
            
            logger.debug(
                "Listed queued outbound messages",
                extra={
                    "channel_id": str(channel_id),
                    "count": len(messages)
                }
            )
            
            return list(messages)
            
        except Exception as e:
            logger.error(
                "Failed to list queued messages",
                extra={"error": str(e), "channel_id": str(channel_id)}
            )
            raise
    
    async def list_by_status(
        self,
        channel_id: UUID,
        status: str,
        limit: int = 100
    ) -> List[OutboundMessage]:
        """
        List outbound messages by status.
        
        Args:
            channel_id: Channel UUID
            status: Message status (queued, sent, delivered, failed, etc.)
            limit: Maximum number of messages to return
            
        Returns:
            List of outbound messages with given status
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            messages = await self.find_all(
                tenant_id=self.tenant_id,
                channel_id=channel_id,
                status=status,
                limit=limit,
                order_by="created_at"
            )
            
            logger.debug(
                "Listed outbound messages by status",
                extra={
                    "channel_id": str(channel_id),
                    "status": status,
                    "count": len(messages)
                }
            )
            
            return list(messages)
            
        except Exception as e:
            logger.error(
                "Failed to list messages by status",
                extra={
                    "error": str(e),
                    "channel_id": str(channel_id),
                    "status": status
                }
            )
            raise
    
    async def list_failed_retryable(
        self,
        channel_id: UUID,
        max_retries: int = 3,
        limit: int = 100
    ) -> List[OutboundMessage]:
        """
        List failed messages that can be retried.
        
        Args:
            channel_id: Channel UUID
            max_retries: Maximum retry count threshold
            limit: Maximum number of messages to return
            
        Returns:
            List of failed messages eligible for retry
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            stmt = select(OutboundMessageModel).where(
                OutboundMessageModel.tenant_id == self.tenant_id,
                OutboundMessageModel.channel_id == channel_id,
                OutboundMessageModel.status == "failed",
                OutboundMessageModel.retry_count < max_retries
            ).order_by(
                OutboundMessageModel.created_at
            ).limit(limit)
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            messages = [self._to_entity(m) for m in models]
            
            logger.debug(
                "Listed failed retryable messages",
                extra={
                    "channel_id": str(channel_id),
                    "count": len(messages)
                }
            )
            
            return messages
            
        except Exception as e:
            logger.error(
                "Failed to list retryable messages",
                extra={"error": str(e), "channel_id": str(channel_id)}
            )
            raise
    
    # ========================================================================
    # OVERRIDE METHODS WITH RLS ENFORCEMENT
    # ========================================================================
    
    async def get_by_id(self, message_id: UUID) -> Optional[OutboundMessage]:
        """Retrieve outbound message by ID with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        return await super().get_by_id(message_id)
    
    async def add(self, entity: OutboundMessage) -> OutboundMessage:
        """Add new outbound message with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().add(entity)
    
    async def update(self, entity: OutboundMessage) -> OutboundMessage:
        """Update outbound message with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().update(entity)
    
    # ========================================================================
    # ENTITY <-> MODEL MAPPING
    # ========================================================================
    
    def _to_entity(self, model: OutboundMessageModel) -> OutboundMessage:
        """Convert ORM model to domain entity."""
        return OutboundMessage(
            id=model.id,
            tenant_id=model.tenant_id,
            channel_id=model.channel_id,
            to_number=model.to_number,
            message_type=model.message_type,
            content=model.content,
            template_id=model.template_id,
            status=model.status,
            wa_message_id=model.wa_message_id,
            error_code=model.error_code,
            error_message=model.error_message,
            retry_count=model.retry_count,
            scheduled_at=model.scheduled_at,
            sent_at=model.sent_at,
            delivered_at=model.delivered_at,
            read_at=model.read_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: OutboundMessage) -> OutboundMessageModel:
        """Convert domain entity to ORM model."""
        return OutboundMessageModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            channel_id=entity.channel_id,
            to_number=entity.to_number,
            message_type=entity.message_type,
            content=entity.content,
            template_id=entity.template_id,
            status=entity.status,
            wa_message_id=entity.wa_message_id,
            error_code=entity.error_code,
            error_message=entity.error_message,
            retry_count=entity.retry_count,
            scheduled_at=entity.scheduled_at,
            sent_at=entity.sent_at,
            delivered_at=entity.delivered_at,
            read_at=entity.read_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )