"""Webhook processing service."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import json

from messaging.domain.interfaces.event_bus import EventBus
from src.messaging.domain.entities.message import Message, MessageDirection, MessageType, MessageStatus
from src.messaging.domain.value_objects.webhook_payload import (
    WebhookMessage, WebhookStatus, WebhookVerification
)
from src.messaging.domain.events.message_events import MessageReceived, MessageDelivered
from src.messaging.domain.interfaces.repositories import MessageRepository, ChannelRepository
from src.messaging.domain.interfaces.external_services import WhatsAppClient, SpeechToTextClient
from src.shared.infrastructure.cache import RedisCache
#from src.shared.infrastructure.events import EventBus
from src.messaging.domain.events.base_event import DomainEvent
logger = logging.getLogger(__name__)


class WebhookService:
    """Service for processing WhatsApp webhook events."""
    
    def __init__(
        self,
        message_repo: MessageRepository,
        channel_repo: ChannelRepository,
        whatsapp_client: WhatsAppClient,
        speech_client: SpeechToTextClient,
        redis_cache: RedisCache,
        event_bus: EventBus
    ):
        self.message_repo = message_repo
        self.channel_repo = channel_repo
        self.whatsapp_client = whatsapp_client
        self.speech_client = speech_client
        self.redis_cache = redis_cache
        self.event_bus = event_bus
    
    async def verify_webhook(
        self,
        mode: str,
        token: str,
        challenge: str,
        expected_token: str
    ) -> Optional[str]:
        """Verify webhook subscription challenge."""
        verification = WebhookVerification(
            mode=mode,
            token=token,
            challenge=challenge
        )
        
        if verification.is_valid(expected_token):
            logger.info("Webhook verification successful")
            return challenge
        
        logger.warning("Webhook verification failed")
        return None
    
    async def verify_signature(
        self,
        signature: str,
        payload: bytes,
        app_secret: str
    ) -> bool:
        """Verify webhook signature."""
        return await self.whatsapp_client.verify_webhook_signature(
            signature,
            payload,
            app_secret
        )
    
    async def process_webhook(
        self,
        tenant_id: uuid.UUID,
        payload: Dict[str, Any]
    ) -> None:
        """Process webhook payload."""
        try:
            # Check if it's a message or status update
            if "messages" in payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}):
                await self._process_message(tenant_id, payload)
            elif "statuses" in payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}):
                await self._process_status(tenant_id, payload)
            else:
                logger.warning(f"Unknown webhook payload type: {payload}")
                
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise
    
    async def _process_message(
        self,
        tenant_id: uuid.UUID,
        payload: Dict[str, Any]
    ) -> None:
        """Process inbound message."""
        try:
            # Extract message data
            value = payload["entry"][0]["changes"][0]["value"]
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
            
            # Get channel
            channels = await self.channel_repo.list_by_tenant(tenant_id)
            channel = next(
                (ch for ch in channels if ch.phone_number_id == phone_number_id),
                None
            )
            
            if not channel:
                logger.error(f"Channel not found for phone_number_id: {phone_number_id}")
                return
            
            # Parse message
            webhook_msg = WebhookMessage.from_webhook_data(value)
            
            # Check for duplicate using idempotency
            idempotency_key = f"wa_msg:{webhook_msg.id}"
            if await self._is_duplicate(idempotency_key):
                logger.info(f"Duplicate message ignored: {webhook_msg.id}")
                return
            
            # Create message entity
            message = Message(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                channel_id=channel.id,
                direction=MessageDirection.INBOUND,
                message_type=self._map_message_type(webhook_msg.type),
                from_number=webhook_msg.from_number,
                to_number=channel.business_phone,
                whatsapp_message_id=webhook_msg.id,
                status=MessageStatus.DELIVERED,
                created_at=webhook_msg.timestamp,
                delivered_at=webhook_msg.timestamp
            )
            
            # Handle different message types
            if webhook_msg.type == "text":
                message.content = webhook_msg.text
                
            elif webhook_msg.type == "audio":
                # Transcribe audio
                if webhook_msg.media_id:
                    media_url = await self.whatsapp_client.get_media_url(
                        webhook_msg.media_id,
                        channel.access_token
                    )
                    if media_url:
                        transcription = await self.speech_client.transcribe_audio(media_url)
                        message.content = transcription or "[Voice message - transcription failed]"
                        message.media_url = media_url
                        
            elif webhook_msg.type in ["image", "video", "document"]:
                # Store media URL
                if webhook_msg.media_id:
                    media_url = await self.whatsapp_client.get_media_url(
                        webhook_msg.media_id,
                        channel.access_token
                    )
                    message.media_url = media_url
                    message.content = f"[{webhook_msg.type.title()} received]"
            
            # Save message
            await self.message_repo.create(message)
            
            # Mark as processed
            await self._mark_processed(idempotency_key)
            
            # Publish event
            event = MessageReceived(
                event_id=uuid.uuid4(),
                aggregate_id=message.id,
                tenant_id=tenant_id,
                occurred_at=datetime.utcnow(),
                channel_id=channel.id,
                from_number=webhook_msg.from_number,
                message_type=message.message_type.value,
                content=message.content,
                whatsapp_message_id=webhook_msg.id
            )
            await self.event_bus.publish(event)
            
            logger.info(f"Processed inbound message {webhook_msg.id} from {webhook_msg.from_number}")
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            raise
    
    async def _process_status(
        self,
        tenant_id: uuid.UUID,
        payload: Dict[str, Any]
    ) -> None:
        """Process delivery status update."""
        try:
            # Extract status data
            value = payload["entry"][0]["changes"][0]["value"]
            webhook_status = WebhookStatus.from_webhook_data(value)
            
            # Find message by WhatsApp ID
            message = await self.message_repo.get_by_whatsapp_id(
                webhook_status.message_id,
                tenant_id
            )
            
            if not message:
                logger.warning(f"Message not found for status update: {webhook_status.message_id}")
                return
            
            # Update message status
            if webhook_status.status == "sent":
                message.mark_sent(webhook_status.message_id)
            elif webhook_status.status == "delivered":
                message.mark_delivered()
            elif webhook_status.status == "read":
                message.mark_read()
            elif webhook_status.status == "failed":
                error = webhook_status.error or {}
                message.mark_failed(
                    str(error.get("code", "unknown")),
                    error.get("title", "Unknown error")
                )
            
            # Save updated message
            await self.message_repo.update(message)
            
            # Publish event if delivered
            if webhook_status.status == "delivered":
                event = MessageDelivered(
                    event_id=uuid.uuid4(),
                    aggregate_id=message.id,
                    tenant_id=tenant_id,
                    occurred_at=webhook_status.timestamp,
                    whatsapp_message_id=webhook_status.message_id,
                    delivered_at=webhook_status.timestamp
                )
                await self.event_bus.publish(event)
            
            logger.info(f"Updated status for message {webhook_status.message_id}: {webhook_status.status}")
            
        except Exception as e:
            logger.error(f"Failed to process status: {e}")
            raise
    
    def _map_message_type(self, webhook_type: str) -> MessageType:
        """Map webhook message type to domain type."""
        type_map = {
            "text": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "audio": MessageType.AUDIO,
            "video": MessageType.VIDEO,
            "document": MessageType.DOCUMENT,
            "location": MessageType.LOCATION,
            "interactive": MessageType.INTERACTIVE,
            "button": MessageType.INTERACTIVE,
            "list": MessageType.INTERACTIVE,
        }
        return type_map.get(webhook_type, MessageType.TEXT)
    
    async def _is_duplicate(self, key: str) -> bool:
        """Check if message is duplicate using Redis."""
        # Try to set key with NX (only if not exists)
        result = await self.redis_cache.set(
            key,
            "1",
            ex=3600,  # 1 hour TTL
            nx=True
        )
        return not result  # If set failed, it's a duplicate
    
    async def _mark_processed(self, key: str) -> None:
        """Mark message as processed."""
        # Key is already set by _is_duplicate
        pass