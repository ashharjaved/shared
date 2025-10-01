"""Get channel statistics query implementation."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class GetChannelStatsQuery:
    """Query to get channel statistics."""
    tenant_id: UUID
    channel_id: UUID
    period: str = "today"  # today, week, month


@dataclass
class ChannelStatsResult:
    """Channel statistics result."""
    channel_id: UUID
    messages_sent: int
    messages_received: int
    messages_delivered: int
    messages_read: int
    messages_failed: int
    avg_delivery_time_seconds: Optional[float]
    template_messages: int
    media_messages: int
    current_month_usage: int
    monthly_limit: Optional[int]
    usage_percentage: Optional[float]
    last_message_at: Optional[datetime]
    active_conversations: int


class GetChannelStatsQueryHandler:
    """Handler for get channel stats query."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def handle(self, query: GetChannelStatsQuery) -> ChannelStatsResult:
        """Execute get channel stats query."""
        try:
            # Calculate date range
            now = datetime.utcnow()
            if query.period == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif query.period == "week":
                start_date = now - timedelta(days=7)
            elif query.period == "month":
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = now - timedelta(days=1)
            
            # Get message statistics
            stats_query = text("""
                SELECT 
                    COUNT(*) FILTER (WHERE direction = 'outbound') as messages_sent,
                    COUNT(*) FILTER (WHERE direction = 'inbound') as messages_received,
                    COUNT(*) FILTER (WHERE status = 'delivered') as messages_delivered,
                    COUNT(*) FILTER (WHERE status = 'read') as messages_read,
                    COUNT(*) FILTER (WHERE status = 'failed') as messages_failed,
                    COUNT(*) FILTER (WHERE message_type = 'template') as template_messages,
                    COUNT(*) FILTER (WHERE message_type IN ('image', 'video', 'audio', 'document')) as media_messages,
                    AVG(EXTRACT(EPOCH FROM (delivered_at - sent_at))) FILTER (WHERE delivered_at IS NOT NULL) as avg_delivery_time,
                    MAX(created_at) as last_message_at,
                    COUNT(DISTINCT CASE WHEN direction = 'inbound' THEN from_number ELSE to_number END) as active_conversations
                FROM messaging.messages
                WHERE channel_id = :channel_id
                    AND tenant_id = :tenant_id
                    AND created_at >= :start_date
            """)
            
            result = await self.session.execute(stats_query, {
                "channel_id": query.channel_id,
                "tenant_id": query.tenant_id,
                "start_date": start_date
            })
            
            stats = result.fetchone()
            
            # Get channel usage info
            channel_query = text("""
                SELECT 
                    current_month_usage,
                    monthly_message_limit
                FROM messaging.channels
                WHERE id = :channel_id
                    AND tenant_id = :tenant_id
            """)
            
            channel_result = await self.session.execute(channel_query, {
                "channel_id": query.channel_id,
                "tenant_id": query.tenant_id
            })
            
            channel = channel_result.fetchone()
            
            # Calculate usage percentage
            usage_percentage = None
            if channel and channel.monthly_message_limit:
                usage_percentage = (channel.current_month_usage / channel.monthly_message_limit) * 100
            
            return ChannelStatsResult(
                channel_id=query.channel_id,
                messages_sent=int(stats.messages_sent) if stats and stats.messages_sent is not None else 0,
                messages_received=int(stats.messages_received) if stats and stats.messages_received is not None else 0,
                messages_delivered=int(stats.messages_delivered) if stats and stats.messages_delivered is not None else 0,
                messages_read=int(stats.messages_read) if stats and stats.messages_read is not None else 0,
                messages_failed=int(stats.messages_failed) if stats and stats.messages_failed is not None else 0,
                avg_delivery_time_seconds=float(stats.avg_delivery_time) if stats and stats.avg_delivery_time is not None else None,
                template_messages=int(stats.template_messages) if stats and stats.template_messages is not None else 0,
                media_messages=int(stats.media_messages) if stats and stats.media_messages is not None else 0,
                current_month_usage=int(channel.current_month_usage) if channel and channel.current_month_usage is not None else 0,
                monthly_limit=int(channel.monthly_message_limit) if channel and channel.monthly_message_limit is not None else None,
                usage_percentage=float(usage_percentage) if usage_percentage is not None else None,
                last_message_at=stats.last_message_at if stats and stats.last_message_at is not None else None,
                active_conversations=int(stats.active_conversations) if stats and stats.active_conversations is not None else 0
            )
            
        except Exception as e:
            logger.error(f"Failed to get channel stats: {e}")
            raise