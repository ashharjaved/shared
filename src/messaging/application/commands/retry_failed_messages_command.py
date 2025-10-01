"""Retry failed messages command implementation."""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
import logging

from src.messaging.domain.interfaces.repositories import MessageRepository
from src.messaging.infrastructure.outbox.outbox_service import OutboxService

logger = logging.getLogger(__name__)


@dataclass
class RetryFailedMessagesCommand:
    """Command to retry failed messages."""
    tenant_id: UUID
    channel_id: Optional[UUID] = None
    max_messages: int = 10
    older_than_minutes: int = 5


class RetryFailedMessagesCommandHandler:
    """Handler for retry failed messages command."""
    
    def __init__(
        self,
        message_repo: MessageRepository,
        outbox_service: OutboxService
    ):
        self.message_repo = message_repo
        self.outbox_service = outbox_service
    
    async def handle(self, command: RetryFailedMessagesCommand) -> int:
        """Execute retry failed messages command."""
        try:
            # Get failed messages eligible for retry
            messages = await self.message_repo.list_pending_outbound(
                command.tenant_id,
                limit=command.max_messages
            )
            
            retry_count = 0
            cutoff_time = datetime.utcnow() - timedelta(minutes=command.older_than_minutes)
            
            for message in messages:
                # Skip if too recent (might still be processing)
                timestamp = message.updated_at or message.created_at
                if timestamp and timestamp > cutoff_time:
                    continue
                
                # Skip if channel doesn't match filter
                if command.channel_id and message.channel_id != command.channel_id:
                    continue
                
                # Skip if max retries exceeded
                if not message.can_retry():
                    continue
                
                # Calculate exponential backoff
                delay_seconds = min(2 ** message.retry_count, 3600)
                scheduled_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
                
                # Queue for retry
                await self.outbox_service.create_event(
                    aggregate_id=message.id,
                    aggregate_type="message",
                    event_type="message.retry",
                    payload={
                        "message_id": str(message.id),
                        "tenant_id": str(command.tenant_id),
                        "retry_count": message.retry_count + 1,
                        "previous_error": message.error_message
                    },
                    tenant_id=command.tenant_id,
                    scheduled_at=scheduled_at
                )
                
                retry_count += 1
                logger.info(f"Queued message {message.id} for retry #{message.retry_count + 1}")
            
            logger.info(f"Queued {retry_count} messages for retry")
            return retry_count
            
        except Exception as e:
            logger.error(f"Failed to retry messages: {e}")
            raise
