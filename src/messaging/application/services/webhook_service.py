"""
Webhook Service
Processes inbound WhatsApp webhooks.
"""
from typing import Dict, Any
from uuid import uuid4
from datetime import datetime

from src.messaging.domain.entities.inbound_message import InboundMessage
from src.messaging.domain.protocols.message_repository import InboundMessageRepository
from src.messaging.domain.protocols.channel_repository import ChannelRepository
from src.messaging.domain.protocols.speech_transcription import SpeechTranscription
from src.messaging.domain.value_objects.webhook_signature import WebhookSignature
from src.messaging.domain.exceptions import (
    InvalidWebhookSignatureError,
    DuplicateMessageError,
    ChannelNotFoundError
)
from src.messaging.infrastructure.idempotency_checker import IdempotencyChecker
from shared.infrastructure.observability.logger import get_logger
from shared.infrastructure.messaging.domain_event_publisher import DomainEventPublisher

logger = get_logger(__name__)


class WebhookService:
    """
    Service for processing WhatsApp webhooks.
    
    Handles verification, message parsing, and idempotency.
    """
    
    def __init__(
        self,
        inbound_repo: InboundMessageRepository,
        channel_repo: ChannelRepository,
        idempotency_checker: IdempotencyChecker,
        event_publisher: DomainEventPublisher,
        transcription_service: SpeechTranscription,
        app_secret: str
    ):
        self.inbound_repo = inbound_repo
        self.channel_repo = channel_repo
        self.idempotency_checker = idempotency_checker
        self.event_publisher = event_publisher
        self.transcription_service = transcription_service
        self.app_secret = app_secret
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify WhatsApp webhook signature.
        
        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value
        
        Returns:
            True if valid, False otherwise
        """
        try:
            WebhookSignature(signature, payload, self.app_secret)
            return True
        except ValueError:
            return False
    
    async def process_webhook(self, payload: Dict[str, Any]) -> None:
        """
        Process incoming webhook payload.
        
        Handles messages, status updates, and other events.
        """
        try:
            # Extract entries
            entries = payload.get("entry", [])
            
            for entry in entries:
                changes = entry.get("changes", [])
                
                for change in changes:
                    value = change.get("value", {})
                    
                    # Process messages
                    if "messages" in value:
                        for message in value["messages"]:
                            await self._process_message(value, message)
                    
                    # Process status updates
                    if "statuses" in value:
                        for status in value["statuses"]:
                            await self._process_status_update(value, status)
        
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
            raise
    
    async def _process_message(
        self, value: Dict[str, Any], message: Dict[str, Any]
    ) -> None:
        """Process inbound message."""
        wa_message_id = message.get("id")
        message_type = message.get("type")
        from_number = message.get("from")
        timestamp = message.get("timestamp")
        
        # Get channel info
        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        to_number = value.get("metadata", {}).get("display_phone_number")
        
        logger.info(
            f"Processing inbound message: {wa_message_id}",
            extra={
                "wa_message_id": wa_message_id,
                "type": message_type,
                "from": from_number
            }
        )
        
        # Find channel
        # In production: cache this lookup
        channels = await self.channel_repo.list_by_tenant(tenant_id=None)  # Need tenant context
        channel = next(
            (c for c in channels if c.phone_number_id == phone_number_id),
            None
        )
        
        if not channel:
            logger.warning(f"Channel not found for phone_number_id: {phone_number_id}")
            raise ChannelNotFoundError(f"No channel configured for {phone_number_id}")
        
        # Check idempotency
        try:
            await self.idempotency_checker.check_and_mark(str(wa_message_id))
        except DuplicateMessageError:
            logger.info(f"Duplicate message ignored: {wa_message_id}")
            return
        
        # Extract content based on type
        content = await self._extract_content(str(message_type), message)
        
        # Create inbound message entity
        inbound_message = InboundMessage(
            id=uuid4(),
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            wa_message_id=str(wa_message_id),
            from_number=str(from_number),
            to_number=to_number,
            message_type=str(message_type),
            content=content,
            timestamp_wa=datetime.fromtimestamp(float(timestamp)),
            raw_payload=message,
            processed=False
        )
        
        # Persist
        await self.inbound_repo.create(inbound_message)
        
        # Publish domain event for conversation engine
        await self.event_publisher.publish_events_from_aggregate.publish(
            event_type="message.received",
            payload={
                "message_id": str(inbound_message.id),
                "tenant_id": str(channel.tenant_id),
                "channel_id": str(channel.id),
                "from_number": from_number,
                "message_type": message_type,
                "content": content
            }
        )
        
        logger.info(f"Inbound message processed: {inbound_message.id}")
    
    async def _extract_content(
        self, message_type: str, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract content based on message type."""
        if message_type == "text":
            return {"body": message.get("text", {}).get("body", "")}
        
        elif message_type == "button":
            return {
                "button_id": message.get("button", {}).get("payload"),
                "button_text": message.get("button", {}).get("text")
            }
        
        elif message_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "list_reply":
                return {
                    "list_reply_id": interactive.get("list_reply", {}).get("id"),
                    "list_reply_title": interactive.get("list_reply", {}).get("title")
                }
            elif interactive.get("type") == "button_reply":
                return {
                    "button_reply_id": interactive.get("button_reply", {}).get("id"),
                    "button_reply_title": interactive.get("button_reply", {}).get("title")
                }
        
        elif message_type == "voice":
            # Handle voice transcription
            voice = message.get("voice", {})
            audio_id = voice.get("id")
            mime_type = voice.get("mime_type")
            
            # Download and transcribe
            # In production: get media URL from WhatsApp API first
            try:
                audio_url = f"https://placeholder/{audio_id}"  # Get from WhatsApp
                transcript = await self.transcription_service.transcribe_audio(audio_url)
                
                return {
                    "audio_id": audio_id,
                    "mime_type": mime_type,
                    "transcript": transcript
                }
            except Exception as e:
                logger.error(f"Transcription failed: {str(e)}")
                return {
                    "audio_id": audio_id,
                    "mime_type": mime_type,
                    "transcript": None,
                    "error": "Transcription failed"
                }
        
        else:
            # Generic content
            return message
    
    async def _process_status_update(
        self, value: Dict[str, Any], status: Dict[str, Any]
    ) -> None:
        """Process delivery status update."""
        wa_message_id = status.get("id")
        status_type = status.get("status")  # sent, delivered, read, failed
        
        logger.info(
            f"Status update: {wa_message_id} -> {status_type}",
            extra={"wa_message_id": wa_message_id, "status": status_type}
        )
        
        # Publish event for outbound message tracking
        await self.event_publisher.publish_events_from_aggregate.publish(
            event_type="message.status_updated",
            payload={
                "wa_message_id": wa_message_id,
                "status": status_type,
                "timestamp": status.get("timestamp")
            }
        )