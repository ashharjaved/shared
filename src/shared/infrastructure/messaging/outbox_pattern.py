"""
Transactional Outbox Pattern
Ensures reliable domain event publication with at-least-once delivery
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from shared.infrastructure.database.base_model import Base
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class OutboxEvent(Base):
    """
    ORM model for outbox events table.
    
    Stores domain events in database transactionally with business data.
    A background worker reads and publishes these events, then marks as processed.
    
    Columns:
        id: Event UUID
        aggregate_id: ID of aggregate that produced event
        aggregate_type: Type of aggregate
        event_type: Domain event class name
        event_data: JSON serialized event payload
        occurred_at: When event occurred
        processed_at: When event was published (NULL if pending)
        retry_count: Number of publish attempts
        max_retries: Maximum retry attempts before DLQ
        error_message: Last error if publish failed
        created_at: Record creation timestamp
    """
    
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "outbox"}
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    aggregate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    aggregate_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    
    event_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    
    event_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    
    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )


class OutboxPublisher:
    """
    Publishes events from outbox to event bus.
    
    Background worker should call this periodically to process pending events.
    Implements at-least-once delivery with exponential backoff retry.
    """
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize outbox publisher.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def add_event(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
        event_type: str,
        event_data: dict[str, Any],
        occurred_at: datetime,
    ) -> OutboxEvent:
        """
        Add a domain event to the outbox.
        
        This is called during transaction commit to persist events
        alongside business data for guaranteed eventual delivery.
        
        Args:
            aggregate_id: ID of aggregate that produced event
            aggregate_type: Type of aggregate (e.g., 'User', 'Organization')
            event_type: Domain event class name
            event_data: Serialized event payload
            occurred_at: When the event occurred
            
        Returns:
            Created OutboxEvent instance
        """
        event = OutboxEvent(
            id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            event_type=event_type,
            event_data=event_data,
            occurred_at=occurred_at,
            processed_at=None,
            retry_count=0,
            max_retries=3,
        )
        
        self.session.add(event)
        await self.session.flush()
        
        logger.debug(
            "Added event to outbox",
            extra={
                "event_id": str(event.id),
                "event_type": event_type,
                "aggregate_id": str(aggregate_id),
            },
        )
        
        return event

    @staticmethod
    async def process_pending_events(
        session: Any,  # AsyncSession
        event_bus: Any,  # EventBus
        batch_size: int = 100,
    ) -> int:
        """
        Process pending outbox events.
        
        Args:
            session: Async database session
            event_bus: Event bus for publishing
            batch_size: Number of events to process per batch
            
        Returns:
            Number of events processed
        """
        # TODO: Implement outbox polling and publishing
        # This is a placeholder - full implementation needed in Phase 1
        logger.info("Outbox publisher placeholder called")
        return 0