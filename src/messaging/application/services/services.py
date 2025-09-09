# src/messaging/application/services.py
import hmac
import hashlib
import base64
import json
from typing import Optional, Dict, Any
from uuid import UUID
import logging

from ..domain.entities import WhatsAppChannel, WhatsAppMessage
from ..domain.value_objects import WhatsAppMessageStatus, WhatsAppMessageDirection
from ..domain.repositories import WhatsAppChannelRepository, WhatsAppMessageRepository
from ..domain.exceptions import (
    InvalidWebhookSignatureException, 
    ChannelNotFoundException,
    InvalidCredentialsException
)

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(
        self,
        channel_repository: WhatsAppChannelRepository,
        message_repository: WhatsAppMessageRepository
    ):
        self.channel_repo = channel_repository
        self.message_repo = message_repository
    
    async def verify_webhook_signature(
        self, 
        raw_body: bytes, 
        signature: str, 
        app_secret: str
    ) -> bool:
        """Verify WhatsApp webhook signature"""
        try:
            # Remove 'sha256=' prefix if present
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            # Compute expected signature
            digest = hmac.new(
                app_secret.encode(), 
                raw_body, 
                hashlib.sha256
            ).digest()
            expected_sig = base64.b64encode(digest).decode()
            
            return hmac.compare_digest(expected_sig, signature)
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    async def process_inbound_message(
        self, 
        event_data: Dict[str, Any], 
        tenant_id: UUID
    ) -> Optional[WhatsAppMessage]:
        """Process inbound WhatsApp message"""
        try:
            # Extract message data from webhook event
            message_data = self._extract_message_data(event_data)
            if not message_data:
                return None
            
            # Check for duplicates
            existing = await self.message_repo.get_by_wa_message_id(message_data['wa_message_id'])
            if existing:
                logger.info(f"Duplicate message {message_data['wa_message_id']} ignored")
                return existing
            
            # Create and save message
            message = WhatsAppMessage(
                tenant_id=tenant_id,
                channel_id=UUID(message_data['channel_id']),
                wa_message_id=message_data['wa_message_id'],
                direction=WhatsAppMessageDirection.INBOUND,
                from_msisdn=message_data['from_msisdn'],
                to_msisdn=message_data['to_msisdn'],
                payload=message_data['payload'],
                status=WhatsAppMessageStatus.RECEIVED,
                created_at=message_data['timestamp']
            )
            
            return await self.message_repo.save(message)
            
        except Exception as e:
            logger.error(f"Failed to process inbound message: {e}")
            raise
    
    def _extract_message_data(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract message data from webhook event"""
        try:
            entry = event_data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            
            messages = value.get('messages', [])
            if not messages:
                return None
            
            message = messages[0]
            return {
                'wa_message_id': message.get('id'),
                'from_msisdn': message.get('from'),
                'to_msisdn': value.get('metadata', {}).get('display_phone_number'),
                'channel_id': value.get('metadata', {}).get('phone_number_id'),
                'timestamp': message.get('timestamp'),
                'payload': message
            }
        except (IndexError, KeyError, TypeError) as e:
            logger.error(f"Failed to extract message data: {e}")
            return None
    
    async def send_message(
        self,
        tenant_id: UUID,
        channel_id: UUID,
        to_msisdn: str,
        message_type: str,
        content: Dict[str, Any],
        template_name: Optional[str] = None
    ) -> WhatsAppMessage:
        """Prepare and queue outbound message"""
        try:
            # Get channel to verify it exists and get credentials
            channel = await self.channel_repo.get_by_id(channel_id)
            if not channel or channel.tenant_id != tenant_id:
                raise ChannelNotFoundException(f"Channel {channel_id} not found")
            
            # Create message entity
            message = WhatsAppMessage(
                tenant_id=tenant_id,
                channel_id=channel_id,
                direction=WhatsAppMessageDirection.OUTBOUND,
                from_msisdn=channel.phone_number_id,
                to_msisdn=to_msisdn,
                payload={
                    'type': message_type,
                    **content,
                    'messaging_product': 'whatsapp'
                },
                template_name=template_name,
                status=WhatsAppMessageStatus.QUEUED
            )
            
            # Save message
            saved_message = await self.message_repo.save(message)
            
            # TODO: Add to outbox for processing
            # await self.outbox_repo.add(outbox_event)
            
            return saved_message
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise