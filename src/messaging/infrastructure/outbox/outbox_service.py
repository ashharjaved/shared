"""Outbox service for reliable message delivery."""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


class OutboxService:
    """Service for managing outbox events."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_event(
        self,
        aggregate_id: uuid.UUID,
        aggregate_type: str,
        event_type: str,
        payload: Dict[str, Any],
        tenant_id: uuid.UUID,
        scheduled_at: Optional[datetime] = None
    ) -> uuid.UUID:
        """Create an outbox event."""
        try:
            event_id = uuid.uuid4()
            
            query = text("""
                INSERT INTO outbox_events (
                    id,
                    aggregate_id,
                    aggregate_type,
                    event_type,
                    payload,
                    tenant_id,
                    created_at,
                    scheduled_at
                ) VALUES (
                    :id,
                    :aggregate_id,
                    :aggregate_type,
                    :event_type,
                    :payload,
                    :tenant_id,
                    :created_at,
                    :scheduled_at
                )
            """)
            
            await self.session.execute(query, {
                "id": event_id,
                "aggregate_id": aggregate_id,
                "aggregate_type": aggregate_type,
                "event_type": event_type,
                "payload": json.dumps(payload),
                "tenant_id": tenant_id,
                "created_at": datetime.utcnow(),
                "scheduled_at": scheduled_at
            })
            
            await self.session.flush()
            
            logger.info(f"Created outbox event {event_id} for {event_type}")
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to create outbox event: {e}")
            raise
    
    async def get_pending_events(self, limit: int = 10) -> list:
        """Get pending events from outbox."""
        try:
            query = text("""
                SELECT 
                    id,
                    aggregate_id,
                    aggregate_type,
                    event_type,
                    payload,
                    tenant_id,
                    retry_count,
                    created_at
                FROM outbox_events
                WHERE processed_at IS NULL
                    AND (scheduled_at IS NULL OR scheduled_at <= :now)
                    AND retry_count < 5
                ORDER BY created_at ASC
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
            """)
            
            result = await self.session.execute(query, {
                "now": datetime.utcnow(),
                "limit": limit
            })
            
            events = []
            for row in result:
                events.append({
                    "id": row.id,
                    "aggregate_id": row.aggregate_id,
                    "aggregate_type": row.aggregate_type,
                    "event_type": row.event_type,
                    "payload": json.loads(row.payload) if row.payload else {},
                    "tenant_id": row.tenant_id,
                    "retry_count": row.retry_count
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get pending events: {e}")
            return []
    
    async def mark_processed(self, event_id: uuid.UUID) -> None:
        """Mark event as processed."""
        try:
            query = text("""
                UPDATE outbox_events
                SET processed_at = :now
                WHERE id = :id
            """)
            
            await self.session.execute(query, {
                "id": event_id,
                "now": datetime.utcnow()
            })
            
            await self.session.flush()
            
        except Exception as e:
            logger.error(f"Failed to mark event as processed: {e}")
            raise
    
    async def mark_failed(self, event_id: uuid.UUID, error_message: str) -> None:
        """Mark event as failed and increment retry count."""
        try:
            query = text("""
                UPDATE outbox_events
                SET 
                    retry_count = retry_count + 1,
                    last_error = :error,
                    updated_at = :now
                WHERE id = :id
            """)
            
            await self.session.execute(query, {
                "id": event_id,
                "error": error_message,
                "now": datetime.utcnow()
            })
            
            await self.session.flush()
            
        except Exception as e:
            logger.error(f"Failed to mark event as failed: {e}")
            raise