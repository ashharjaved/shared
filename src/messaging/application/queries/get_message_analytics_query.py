"""Get message analytics query implementation."""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class GetMessageAnalyticsQuery:
    """Query to get message analytics."""
    tenant_id: UUID
    channel_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    granularity: str = "day"  # hour, day, week, month


@dataclass
class MessageAnalyticsResult:
    """Message analytics result."""
    period: str
    total_messages: int
    sent_messages: int
    received_messages: int
    delivered_rate: float
    read_rate: float
    failed_rate: float
    avg_response_time_minutes: Optional[float]
    peak_hour: Optional[int]
    top_message_types: List[Dict[str, Any]]
    time_series: List[Dict[str, Any]]


class GetMessageAnalyticsQueryHandler:
    """Handler for get message analytics query."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def handle(self, query: GetMessageAnalyticsQuery) -> MessageAnalyticsResult:
        """Execute get message analytics query."""
        try:
            # Set default date range
            if not query.end_date:
                query.end_date = datetime.utcnow()
            if not query.start_date:
                query.start_date = query.end_date - timedelta(days=30)
            
            # Get overall statistics
            stats = await self._get_overall_stats(query)
            
            # Get time series data
            time_series = await self._get_time_series(query)
            
            # Get top message types
            top_types = await self._get_top_message_types(query)
            
            # Get peak hour
            peak_hour = await self._get_peak_hour(query)
            
            # Get average response time
            avg_response = await self._get_avg_response_time(query)
            
            # Calculate rates
            delivered_rate = 0
            read_rate = 0
            failed_rate = 0
            
            if stats['sent_messages'] > 0:
                delivered_rate = (stats['delivered_messages'] / stats['sent_messages']) * 100
                read_rate = (stats['read_messages'] / stats['sent_messages']) * 100
                failed_rate = (stats['failed_messages'] / stats['sent_messages']) * 100
            
            period = f"{query.start_date.date()} to {query.end_date.date()}"
            
            return MessageAnalyticsResult(
                period=period,
                total_messages=stats['total_messages'],
                sent_messages=stats['sent_messages'],
                received_messages=stats['received_messages'],
                delivered_rate=round(delivered_rate, 2),
                read_rate=round(read_rate, 2),
                failed_rate=round(failed_rate, 2),
                avg_response_time_minutes=avg_response,
                peak_hour=peak_hour,
                top_message_types=top_types,
                time_series=time_series
            )
            
        except Exception as e:
            logger.error(f"Failed to get message analytics: {e}")
            raise
    
    async def _get_overall_stats(self, query: GetMessageAnalyticsQuery) -> Dict[str, int]:
        """Get overall message statistics."""
        conditions = ["tenant_id = :tenant_id"]
        params = {
            "tenant_id": query.tenant_id,
            "start_date": query.start_date,
            "end_date": query.end_date
        }
        
        if query.channel_id:
            conditions.append("channel_id = :channel_id")
            params["channel_id"] = query.channel_id
        
        conditions.append("created_at BETWEEN :start_date AND :end_date")
        
        stats_query = text(f"""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(*) FILTER (WHERE direction = 'outbound') as sent_messages,
                COUNT(*) FILTER (WHERE direction = 'inbound') as received_messages,
                COUNT(*) FILTER (WHERE status = 'delivered') as delivered_messages,
                COUNT(*) FILTER (WHERE status = 'read') as read_messages,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_messages
            FROM messaging.messages
            WHERE {' AND '.join(conditions)}
        """)
        
        result = await self.session.execute(stats_query, params)
        row = result.fetchone()
        
        return {
            "total_messages": row.total_messages or 0,
            "sent_messages": row.sent_messages or 0,
            "received_messages": row.received_messages or 0,
            "delivered_messages": row.delivered_messages or 0,
            "read_messages": row.read_messages or 0,
            "failed_messages": row.failed_messages or 0
        }
    
    async def _get_time_series(self, query: GetMessageAnalyticsQuery) -> List[Dict[str, Any]]:
        """Get time series data."""
        # Determine date truncation based on granularity
        if query.granularity == "hour":
            date_trunc = "hour"
        elif query.granularity == "week":
            date_trunc = "week"
        elif query.granularity == "month":
            date_trunc = "month"
        else:
            date_trunc = "day"
        
        conditions = ["tenant_id = :tenant_id"]
        params = {
            "tenant_id": query.tenant_id,
            "start_date": query.start_date,
            "end_date": query.end_date
        }
        
        if query.channel_id:
            conditions.append("channel_id = :channel_id")
            params["channel_id"] = query.channel_id
        
        conditions.append("created_at BETWEEN :start_date AND :end_date")
        
        series_query = text(f"""
            SELECT 
                DATE_TRUNC('{date_trunc}', created_at) as period,
                COUNT(*) FILTER (WHERE direction = 'outbound') as sent,
                COUNT(*) FILTER (WHERE direction = 'inbound') as received,
                COUNT(*) FILTER (WHERE status = 'delivered') as delivered,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM messaging.messages
            WHERE {' AND '.join(conditions)}
            GROUP BY period
            ORDER BY period ASC
        """)
        
        result = await self.session.execute(series_query, params)
        
        time_series = []
        for row in result:
            time_series.append({
                "period": row.period.isoformat(),
                "sent": row.sent or 0,
                "received": row.received or 0,
                "delivered": row.delivered or 0,
                "failed": row.failed or 0
            })
        
        return time_series
    
    async def _get_top_message_types(self, query: GetMessageAnalyticsQuery) -> List[Dict[str, Any]]:
        """Get top message types."""
        conditions = ["tenant_id = :tenant_id"]
        params = {
            "tenant_id": query.tenant_id,
            "start_date": query.start_date,
            "end_date": query.end_date
        }
        
        if query.channel_id:
            conditions.append("channel_id = :channel_id")
            params["channel_id"] = query.channel_id
        
        conditions.append("created_at BETWEEN :start_date AND :end_date")
        
        types_query = text(f"""
            SELECT 
                message_type,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
            FROM messaging.messages
            WHERE {' AND '.join(conditions)}
            GROUP BY message_type
            ORDER BY count DESC
            LIMIT 5
        """)
        
        result = await self.session.execute(types_query, params)
        
        top_types = []
        for row in result:
            top_types.append({
                "type": row.message_type,
                "count": row.count,
                "percentage": float(row.percentage)
            })
        
        return top_types
    
    async def _get_peak_hour(self, query: GetMessageAnalyticsQuery) -> Optional[int]:
        """Get peak message hour."""
        conditions = ["tenant_id = :tenant_id"]
        params = {
            "tenant_id": query.tenant_id,
            "start_date": query.start_date,
            "end_date": query.end_date
        }
        
        if query.channel_id:
            conditions.append("channel_id = :channel_id")
            params["channel_id"] = query.channel_id
        
        conditions.append("created_at BETWEEN :start_date AND :end_date")
        
        peak_query = text(f"""
            SELECT 
                EXTRACT(HOUR FROM created_at) as hour,
                COUNT(*) as count
            FROM messaging.messages
            WHERE {' AND '.join(conditions)}
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """)
        
        result = await self.session.execute(peak_query, params)
        row = result.fetchone()
        
        return int(row.hour) if row else None
    
    async def _get_avg_response_time(self, query: GetMessageAnalyticsQuery) -> Optional[float]:
        """Get average response time to inbound messages."""
        conditions = ["m1.tenant_id = :tenant_id"]
        params = {
            "tenant_id": query.tenant_id,
            "start_date": query.start_date,
            "end_date": query.end_date
        }
        
        if query.channel_id:
            conditions.append("m1.channel_id = :channel_id")
            params["channel_id"] = query.channel_id
        
        conditions.append("m1.created_at BETWEEN :start_date AND :end_date")
        
        response_query = text(f"""
            WITH conversation_pairs AS (
                SELECT 
                    m1.created_at as inbound_time,
                    MIN(m2.created_at) as response_time
                FROM messaging.messages m1
                JOIN messaging.messages m2 ON 
                    m1.from_number = m2.to_number
                    AND m1.to_number = m2.from_number
                    AND m2.direction = 'outbound'
                    AND m2.created_at > m1.created_at
                    AND m2.created_at < m1.created_at + INTERVAL '1 hour'
                WHERE m1.direction = 'inbound'
                    AND {' AND '.join(conditions)}
                GROUP BY m1.id, m1.created_at
            )
            SELECT AVG(EXTRACT(EPOCH FROM (response_time - inbound_time)) / 60) as avg_minutes
            FROM conversation_pairs
            WHERE response_time IS NOT NULL
        """)
        
        result = await self.session.execute(response_query, params)
        row = result.fetchone()
        
        return round(row.avg_minutes, 2) if row and row.avg_minutes else None