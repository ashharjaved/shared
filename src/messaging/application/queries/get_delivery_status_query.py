"""Get delivery status query implementation."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging

from src.messaging.domain.interfaces.repositories import MessageRepository
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class GetDeliveryStatusQuery:
    """Query to get delivery status."""
    tenant_id: UUID
    message_id: Optional[UUID] = None
    whatsapp_message_id: Optional[str] = None
    include_history: bool = False


@dataclass
class DeliveryStatusResult:
    """Delivery status result."""
    message_id: UUID
    whatsapp_message_id: Optional[str]
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    failed_at: Optional[datetime]
    error_code: Optional[str]
    error_message: Optional[str]
    retry_count: int
    history: Optional[List[Dict[str, Any]]] = None


class GetDeliveryStatusQueryHandler:
    """Handler for get delivery status query."""
    
    def __init__(
        self,
        message_repo: MessageRepository,
        session: AsyncSession
    ):
        self.message_repo = message_repo
        self.session = session
    
    async def handle(self, query: GetDeliveryStatusQuery) -> Optional[DeliveryStatusResult]:
        """Execute get delivery status query."""
        try:
            # Get message
            message = None
            if query.message_id:
                message = await self.message_repo.get_by_id(query.message_id, query.tenant_id)
            elif query.whatsapp_message_id:
                message = await self.message_repo.get_by_whatsapp_id(
                    query.whatsapp_message_id,
                    query.tenant_id
                )
            
            if not message:
                return None
            
            # Get delivery history if requested
            history = None
            if query.include_history:
                history = await self._get_delivery_history(message.id)
            
            return DeliveryStatusResult(
                message_id=message.id,
                whatsapp_message_id=message.whatsapp_message_id,
                status=message.status.value,
                sent_at=message.sent_at,
                delivered_at=message.delivered_at,
                read_at=message.read_at,
                failed_at=message.updated_at if message.status.value == "failed" else None,
                error_code=message.error_code,
                error_message=message.error_message,
                retry_count=message.retry_count,
                history=history
            )
            
        except Exception as e:
            logger.error(f"Failed to get delivery status: {e}")
            raise
    
    async def _get_delivery_history(self, message_id: UUID) -> List[Dict[str, Any]]:
        """Get delivery status history."""
        query = text("""
            SELECT 
                status,
                timestamp,
                error_code,
                error_message,
                created_at
            FROM messaging.delivery_status
            WHERE message_id = :message_id
            ORDER BY timestamp DESC
        """)
        
        result = await self.session.execute(query, {"message_id": message_id})
        
        history = []
        for row in result:
            history.append({
                "status": row.status,
                "timestamp": row.timestamp.isoformat(),
                "error_code": row.error_code,
                "error_message": row.error_message
            })
        
        return history