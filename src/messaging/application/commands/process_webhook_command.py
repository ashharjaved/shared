"""Process webhook command implementation."""

from dataclasses import dataclass
from typing import Dict, Any
from uuid import UUID
from datetime import datetime
import logging
import json

from src.messaging.domain.entities.message import Message, MessageDirection, MessageType, MessageStatus
from src.messaging.domain.value_objects.webhook_payload import WebhookMessage, WebhookStatus
from src.messaging.domain.events.message_events import MessageReceived, MessageDelivered, MessageRead
from src.messaging.domain.interfaces.repositories import MessageRepository, ChannelRepository
from src.messaging.infrastructure.cache.redis_cache import MessagingCache
from src.messaging.infrastructure.events.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class ProcessWebhookCommand:
    """Command to process webhook event."""
    tenant_id: UUID
    channel_id: UUID
    event_type: str  # message, status, error
    payload: Dict[str, Any]


class ProcessWebhookCommandHandler:
    """Handler for process webhook command."""
    
    def __init__(
        self,
        message_repo: MessageRepository,
        channel_repo: ChannelRepository,
        cache: MessagingCache,
        event_bus: EventBus
    ):
        self.message_repo = message_repo
        self.channel_repo = channel_repo
        self.cache = cache
        self.event_bus = event_bus
    
    async def handle(self, command: ProcessWebhookCommand) -> None:
        """Execute process webhook command."""
        try:
            if command.event_type == "message":
                await self._process_message(command)
            elif command.event_type == "status":
                await self._process_status(command)
            elif command.event_type == "error":
                await self._process_error(command)
            else:
                logger.warning(f"Unknown webhook event type: {command.event_type}")
                
        except Exception as e:
            logger.error(f"Failed to process webhook: {e}")
            raise
    
    async def _process_message(self, command: ProcessWebhookCommand) -> None:
        """Process inbound message."""
        try:
            # Parse webhook message
            webhook_msg = WebhookMessage.from_webhook_data(command.payload)
            
            # Check for duplicate
            is_duplicate = await self.cache.is_webhook_processed(webhook_msg.id)
            if is_duplicate:
                logger.info(f"Duplicate webhook message ignored: {webhook_msg.id}")
                return
            
            # Get channel
            channel = await self.channel_repo.get_by_id(command.channel_id, command.tenant_id)
            if not channel:
                logger.error(f"Channel {command.channel_id} not found")
                return
            
            # Map message type
            message_type = self._map_webhook_type(webhook_msg.type)
            
            # Create message entity
            message = Message(
                id=UUID(),
                tenant_id=command.tenant_id,
                channel_id=command.channel_id,
                direction=MessageDirection.INBOUND,
                message_type=message_type,
                from_number=webhook_msg.from_number,
                to_number=channel.business_phone,
                content=webhook_msg.text,
                media_url=webhook_msg.media_url,
                whatsapp_message_id=webhook_msg.id,
                status=MessageStatus.DELIVERED,
                metadata={"context": webhook_msg.context} if webhook_msg.context else None,
                created_at=webhook_msg.timestamp,
                delivered_at=webhook_msg.timestamp
            )
            
            # Save message
            await self.message_repo.create(message)
            
            # Update session window
            await self.cache.set_session_window(
                webhook_msg.from_number,
                webhook_msg.timestamp.isoformat()
            )
            
            # Publish event
            event = MessageReceived(
                event_id=UUID(),
                aggregate_id=message.id,
                tenant_id=command.tenant_id,
                occurred_at=datetime.utcnow(),
                channel_id=command.channel_id,
                from_number=webhook_msg.from_number,
                message_type=message_type.value,
                content=message.content,
                whatsapp_message_id=webhook_msg.id
            )
            await self.event_bus.publish(event)
            
            logger.info(f"Processed inbound message {webhook_msg.id} from {webhook_msg.from_number}")
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            raise
    
    async def _process_status(self, command: ProcessWebhookCommand) -> None:
        """Process delivery status update."""
        try:
            # Parse status update
            webhook_status = WebhookStatus.from_webhook_data(command.payload)
            
            # Find message
            message = await self.message_repo.get_by_whatsapp_id(
                webhook_status.message_id,
                command.tenant_id
            )
            
            if not message:
                logger.warning(f"Message not found for status: {webhook_status.message_id}")
                return
            
            # Update message status
            previous_status = message.status
            
            if webhook_status.status == "sent":
                message.mark_sent(webhook_status.message_id)
            elif webhook_status.status == "delivered":
                message.mark_delivered()
                # Publish delivered event
                event = MessageDelivered(
                    event_id=UUID(),
                    aggregate_id=message.id,
                    tenant_id=command.tenant_id,
                    occurred_at=webhook_status.timestamp,
                    whatsapp_message_id=webhook_status.message_id,
                    delivered_at=webhook_status.timestamp
                )
                await self.event_bus.publish(event)
            elif webhook_status.status == "read":
                message.mark_read()
                # Publish read event
                event = MessageRead(
                    event_id=UUID(),
                    aggregate_id=message.id,
                    tenant_id=command.tenant_id,
                    occurred_at=webhook_status.timestamp,
                    whatsapp_message_id=webhook_status.message_id,
                    read_at=webhook_status.timestamp
                )
                await self.event_bus.publish(event)
            elif webhook_status.status == "failed":
                error = webhook_status.error or {}
                message.mark_failed(
                    str(error.get("code", "unknown")),
                    error.get("message", "Unknown error")
                )
            
            # Save updated message
            await self.message_repo.update(message)
            
            logger.info(f"Updated message {message.id} status: {previous_status} -> {message.status}")
            
        except Exception as e:
            logger.error(f"Failed to process status: {e}")
            raise
    
    async def _process_error(self, command: ProcessWebhookCommand) -> None:
        """Process error notification."""
        try:
            error_data = command.payload
            logger.error(f"WhatsApp error received: {json.dumps(error_data)}")
            
            errors = error_data.get("errors") or []
            primary_error = errors[0] if errors else error_data
            raw_error_data = primary_error.get("error_data") or {}
            error_code = str(primary_error.get("code", "")).lower()
            error_parts = [
                primary_error.get("title"),
                primary_error.get("message"),
                raw_error_data.get("details"),
                raw_error_data.get("reason"),
                primary_error.get("type"),
            ]
            error_subcode = primary_error.get("error_subcode")
            if error_subcode:
                error_parts.append(str(error_subcode))
            description = ' '.join(part.lower() for part in error_parts if part)
            detail_text = (
                raw_error_data.get("details")
                or primary_error.get("message")
                or primary_error.get("title")
                or ""
            )
            rate_limit_codes = {"4", "613", "80007", "131029", "131031"}
            invalid_token_codes = {"190", "102", "104"}
            suspension_codes = {"200", "131000", "131005", "131026"}
            rate_limit_hit = any(term in description for term in ("rate limit", "too many requests", "throttle", "call limit")) or error_code in rate_limit_codes
            invalid_token_error = any(term in description for term in ("invalid token", "access token", "token expired", "token has expired")) or error_code in invalid_token_codes
            account_suspended = any(term in description for term in ("suspend", "disabled", "blocked", "ban")) or error_code in suspension_codes
            if rate_limit_hit:
                now_ts = datetime.utcnow().timestamp()
                retry_after = raw_error_data.get("retry_after")
                try:
                    last_refill = now_ts + float(retry_after)
                except (TypeError, ValueError):
                    last_refill = now_ts
                await self.cache.set_rate_limit_info(str(command.channel_id), 0, last_refill)
                logger.warning(f"Rate limit encountered for channel {command.channel_id}: {detail_text or 'rate limit'}")
            if invalid_token_error or account_suspended:
                channel = await self.channel_repo.get_by_id(command.channel_id, command.tenant_id)
                if not channel:
                    logger.warning(f"Channel {command.channel_id} not found while processing webhook error")
                else:
                    if account_suspended:
                        channel.suspend(detail_text or "Account suspended by provider")
                        logger.error(f"Channel {channel.id} suspended due to provider notification: {detail_text or 'suspended'}")
                    elif invalid_token_error:
                        channel.deactivate()
                        logger.error(f"Channel {channel.id} deactivated due to invalid token notification")
                    await self.channel_repo.update(channel)
                    await self.cache.delete_channel(str(channel.id))
            
        except Exception as e:
            logger.error(f"Failed to process error: {e}")
            raise
    
    def _map_webhook_type(self, webhook_type: str) -> MessageType:
        """Map webhook message type to domain type."""
        type_map = {
            "text": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "audio": MessageType.AUDIO,
            "voice": MessageType.AUDIO,
            "video": MessageType.VIDEO,
            "document": MessageType.DOCUMENT,
            "location": MessageType.LOCATION,
            "sticker": MessageType.IMAGE,
            "contacts": MessageType.TEXT,
            "interactive": MessageType.INTERACTIVE,
            "button": MessageType.INTERACTIVE,
            "list": MessageType.INTERACTIVE,
        }
        return type_map.get(webhook_type, MessageType.TEXT)