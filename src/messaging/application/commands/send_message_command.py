"""Send message command implementation."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import logging

from src.messaging.domain.entities.message import Message, MessageDirection, MessageType, MessageStatus
from src.messaging.domain.interfaces.repositories import MessageRepository, ChannelRepository, TemplateRepository
from messaging.domain.protocols.external_services import WhatsAppClient
from src.messaging.infrastructure.rate_limiter.token_bucket import TokenBucketRateLimiter
from src.messaging.infrastructure.outbox.outbox_service import OutboxService

logger = logging.getLogger(__name__)


@dataclass
class SendMessageCommand:
    """Command to send a WhatsApp message."""
    tenant_id: UUID
    channel_id: UUID
    to_number: str
    content: Optional[str] = None
    template_name: Optional[str] = None
    template_variables: Optional[Dict[str, str]] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    idempotency_key: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class SendMessageCommandHandler:
    """Handler for send message command."""
    
    def __init__(
        self,
        message_repo: MessageRepository,
        channel_repo: ChannelRepository,
        template_repo: TemplateRepository,
        rate_limiter: TokenBucketRateLimiter,
        outbox_service: OutboxService
    ):
        self.message_repo = message_repo
        self.channel_repo = channel_repo
        self.template_repo = template_repo
        self.rate_limiter = rate_limiter
        self.outbox_service = outbox_service
    
    async def handle(self, command: SendMessageCommand) -> Message:
        """Execute send message command."""
        try:
            # Validate channel
            channel = await self.channel_repo.get_by_id(command.channel_id, command.tenant_id)
            if not channel:
                raise ValueError(f"Channel {command.channel_id} not found")
            
            if not channel.can_send_message():
                raise ValueError(f"Channel {command.channel_id} cannot send messages: {channel.status}")
            
            # Check rate limit
            rate_key = f"channel:{channel.id}"
            allowed, tokens = await self.rate_limiter.is_allowed(
                rate_key,
                channel.rate_limit_per_second,
                burst=channel.rate_limit_per_second * 2
            )
            
            if not allowed:
                raise ValueError(f"Rate limit exceeded. Tokens remaining: {tokens}")
            
            # Check session window
            last_inbound = await self.message_repo.get_last_inbound_time(
                command.to_number,
                command.tenant_id
            )
            
            within_session = False
            if last_inbound:
                time_diff = datetime.utcnow() - last_inbound
                within_session = time_diff.total_seconds() < 24 * 60 * 60
            
            # Determine message type
            message_type = self._determine_message_type(
                command.content,
                command.template_name,
                command.media_url,
                command.media_type
            )
            
            # Validate template if needed
            template_id = None
            if command.template_name and not within_session:
                template = await self.template_repo.get_by_name(
                    command.template_name,
                    command.channel_id,
                    command.tenant_id
                )
                
                if not template:
                    raise ValueError(f"Template {command.template_name} not found")
                
                if not template.can_be_used():
                    raise ValueError(f"Template {command.template_name} is not approved")
                
                if command.template_variables:
                    if not template.validate_variables(command.template_variables):
                        raise ValueError("Invalid template variables")
                
                template_id = template.id
            elif not within_session and not command.template_name:
                raise ValueError("Messages outside 24-hour session window require a template")
            
            # Create message entity
            message = Message(
                id=UUID() if not command.idempotency_key else UUID(command.idempotency_key[:36]),
                tenant_id=command.tenant_id,
                channel_id=command.channel_id,
                direction=MessageDirection.OUTBOUND,
                message_type=message_type,
                from_number=channel.business_phone,
                to_number=command.to_number,
                content=command.content,
                media_url=command.media_url,
                template_id=template_id,
                template_variables=command.template_variables,
                status=MessageStatus.QUEUED,
                created_at=datetime.utcnow()
            )
            
            # Save message
            message = await self.message_repo.create(message)
            
            # Queue for processing
            await self.outbox_service.create_event(
                aggregate_id=message.id,
                aggregate_type="message",
                event_type="message.send_requested",
                payload={
                    "message_id": str(message.id),
                    "tenant_id": str(command.tenant_id),
                    "channel_id": str(command.channel_id),
                    "priority": "high" if message_type == MessageType.TEMPLATE else "normal"
                },
                tenant_id=command.tenant_id,
                scheduled_at=command.scheduled_at
            )
            
            logger.info(f"Message {message.id} queued for sending to {command.to_number}")
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to handle send message command: {e}")
            raise
    
    def _determine_message_type(
        self,
        content: Optional[str],
        template_name: Optional[str],
        media_url: Optional[str],
        media_type: Optional[str]
    ) -> MessageType:
        """Determine message type from content."""
        if template_name:
            return MessageType.TEMPLATE
        elif media_url:
            if media_type:
                return MessageType[media_type.upper()]
            # Guess from URL extension
            if media_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                return MessageType.IMAGE
            elif media_url.lower().endswith(('.mp4', '.avi', '.mov')):
                return MessageType.VIDEO
            elif media_url.lower().endswith(('.mp3', '.wav', '.ogg')):
                return MessageType.AUDIO
            else:
                return MessageType.DOCUMENT
        else:
            return MessageType.TEXT