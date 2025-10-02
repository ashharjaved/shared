"""Message sending and management service."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid
import asyncio
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.domain.entities.message import Message, MessageDirection, MessageType, MessageStatus
from src.messaging.domain.entities.template import MessageTemplate
from src.messaging.domain.value_objects.phone_number import PhoneNumber
from src.messaging.domain.interfaces.repositories import (
    MessageRepository, ChannelRepository, TemplateRepository
)
from messaging.domain.protocols.external_services import (
    WhatsAppClient, WhatsAppMessageRequest, WhatsAppMessageResponse
)
from src.messaging.infrastructure.rate_limiter.token_bucket import TokenBucketRateLimiter
from src.messaging.domain.events.message_events import MessageSent, MessageFailed
from src.messaging.infrastructure.events.event_bus import EventBus
from src.messaging.infrastructure.outbox.outbox_service import OutboxService

logger = logging.getLogger(__name__)


class MessageService:
    """Service for sending WhatsApp messages."""
    
    def __init__(
        self,
        message_repo: MessageRepository,
        channel_repo: ChannelRepository,
        template_repo: TemplateRepository,
        whatsapp_client: WhatsAppClient,
        rate_limiter: TokenBucketRateLimiter,
        event_bus: EventBus,
        outbox_service: OutboxService,
        session: AsyncSession
    ):
        self.message_repo = message_repo
        self.channel_repo = channel_repo
        self.template_repo = template_repo
        self.whatsapp_client = whatsapp_client
        self.rate_limiter = rate_limiter
        self.event_bus = event_bus
        self.outbox_service = outbox_service
        self.session = session
    
    async def send_message(
        self,
        tenant_id: uuid.UUID,
        channel_id: uuid.UUID,
        to_number: str,
        content: Optional[str] = None,
        template_name: Optional[str] = None,
        template_variables: Optional[Dict[str, str]] = None,
        media_url: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Message:
        """Send a WhatsApp message."""
        try:
            # Validate phone number
            phone = PhoneNumber(to_number)
            
            # Get channel
            channel = await self.channel_repo.get_by_id(channel_id, tenant_id)
            if not channel:
                raise ValueError(f"Channel {channel_id} not found")
            
            if not channel.can_send_message():
                raise ValueError(f"Channel {channel_id} cannot send messages")
            
            # Check if within session window (24 hours)
            last_inbound_time = await self.message_repo.get_last_inbound_time(
                to_number,
                tenant_id
            )
            
            within_session = False
            if last_inbound_time:
                time_diff = datetime.utcnow() - last_inbound_time
                within_session = time_diff.total_seconds() < 24 * 60 * 60
            
            # Determine message type
            message_type = MessageType.TEXT
            if media_url:
                # Determine media type from URL or metadata
                message_type = MessageType.IMAGE  # Simplified
            elif template_name:
                message_type = MessageType.TEMPLATE
            
            # Create message entity
            message = Message(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                channel_id=channel_id,
                direction=MessageDirection.OUTBOUND,
                message_type=message_type,
                from_number=channel.business_phone,
                to_number=to_number,
                content=content,
                media_url=media_url,
                template_variables=template_variables,
                status=MessageStatus.QUEUED,
                created_at=datetime.utcnow()
            )
            
            # If template message, validate and prepare
            template = None
            if template_name and not within_session:
                template = await self.template_repo.get_by_name(
                    template_name,
                    channel_id,
                    tenant_id
                )
                
                if not template:
                    raise ValueError(f"Template {template_name} not found")
                
                if not template.can_be_used():
                    raise ValueError(f"Template {template_name} is not approved")
                
                if template_variables and not template.validate_variables(template_variables):
                    raise ValueError(f"Invalid template variables")
                
                message.template_id = template.id
            elif not within_session and not template_name:
                raise ValueError("Message outside session window requires template")
            
            # Save message to create outbox event
            message = await self.message_repo.create(message)
            
            # Queue for async sending via outbox
            await self.outbox_service.create_event(
                aggregate_id=message.id,
                aggregate_type="message",
                event_type="message.send_requested",
                payload={
                    "message_id": str(message.id),
                    "tenant_id": str(tenant_id),
                    "channel_id": str(channel_id)
                },
                tenant_id=tenant_id
            )
            
            logger.info(f"Message {message.id} queued for sending to {to_number}")
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    async def process_outbound_message(
        self,
        message_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> None:
        """Process outbound message from queue (called by worker)."""
        try:
            # Get message
            message = await self.message_repo.get_by_id(message_id, tenant_id)
            if not message:
                logger.error(f"Message {message_id} not found")
                return
            
            # Skip if already sent or failed permanently
            if message.status in [MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ]:
                logger.info(f"Message {message_id} already sent")
                return
            
            if message.status == MessageStatus.FAILED and not message.can_retry():
                logger.warning(f"Message {message_id} cannot be retried")
                return
            
            # Get channel
            channel = await self.channel_repo.get_by_id(message.channel_id, tenant_id)
            if not channel:
                logger.error(f"Channel {message.channel_id} not found")
                return
            
            # Check rate limit
            rate_limit_key = f"channel:{channel.id}"
            allowed, tokens_remaining = await self.rate_limiter.is_allowed(
                rate_limit_key,
                channel.rate_limit_per_second
            )
            
            if not allowed:
                # Requeue with delay
                logger.warning(f"Rate limit exceeded for channel {channel.id}, requeuing")
                await self._requeue_message(message, delay_seconds=1)
                return
            
            # Build WhatsApp request
            request = await self._build_whatsapp_request(message, channel)
            
            # Send via WhatsApp API
            response = await self.whatsapp_client.send_message(
                channel.phone_number_id,
                channel.access_token,
                request
            )
            
            if response.success:
                # Mark as sent
                message.mark_sent(response.message_id)
                await self.message_repo.update(message)
                
                # Update channel usage
                channel.increment_usage()
                await self.channel_repo.update(channel)
                
                # Publish event
                event = MessageSent(
                    event_id=uuid.uuid4(),
                    aggregate_id=message.id,
                    tenant_id=tenant_id,
                    occurred_at=datetime.utcnow(),
                    channel_id=channel.id,
                    to_number=message.to_number,
                    message_type=message.message_type.value,
                    whatsapp_message_id=response.message_id
                )
                await self.event_bus.publish(event)
                
                logger.info(f"Message {message_id} sent successfully: {response.message_id}")
                
            else:
                # Mark as failed
                message.mark_failed(
                    response.error_code or "unknown",
                    response.error_message or "Unknown error"
                )
                await self.message_repo.update(message)
                
                # Retry if possible
                if message.can_retry():
                    delay = self._calculate_retry_delay(message.retry_count)
                    await self._requeue_message(message, delay_seconds=delay)
                    logger.warning(f"Message {message_id} failed, retrying in {delay}s")
                else:
                    # Permanent failure
                    event = MessageFailed(
                        event_id=uuid.uuid4(),
                        aggregate_id=message.id,
                        tenant_id=tenant_id,
                        occurred_at=datetime.utcnow(),
                        channel_id=channel.id,
                        to_number=message.to_number,
                        error_code=response.error_code or "unknown",
                        error_message=response.error_message or "Unknown error",
                        retry_count=message.retry_count
                    )
                    await self.event_bus.publish(event)
                    logger.error(f"Message {message_id} permanently failed: {response.error_message}")
                    
        except Exception as e:
            logger.error(f"Failed to process outbound message {message_id}: {e}")
            # Requeue with delay
            try:
                message = await self.message_repo.get_by_id(message_id, tenant_id)
                if message and message.can_retry():
                    await self._requeue_message(message, delay_seconds=60)
            except:
                pass
    
    async def _build_whatsapp_request(
        self,
        message: Message,
        channel: Any
    ) -> WhatsAppMessageRequest:
        """Build WhatsApp API request from message."""
        request = WhatsAppMessageRequest(
            to=message.to_number,
            type="text"
        )
        
        if message.message_type == MessageType.TEXT:
            request.text = message.content
            
        elif message.message_type == MessageType.TEMPLATE:
            template_id = message.template_id
            if template_id is not None:
                template = await self.template_repo.get_by_id(template_id, message.tenant_id)
                if template:
                    request.type = "template"
                    request.template_name = template.name
                    request.template_language = template.language
                    
                    # Build components with variables
                    if message.template_variables:
                        components = []
                        for comp in template.components:
                            if comp.type == "body" and comp.text:
                                # Replace variables
                                parameters = []
                                for var_key in sorted(message.template_variables.keys()):
                                    parameters.append({
                                        "type": "text",
                                        "text": message.template_variables[var_key]
                                    })
                                if parameters:
                                    components.append({
                                        "type": "body",
                                        "parameters": parameters
                                    })
                        request.template_components = components
                        
        elif message.message_type == MessageType.IMAGE:
            request.type = "image"
            request.media_url = message.media_url
            
        return request
    
    async def _requeue_message(self, message: Message, delay_seconds: int) -> None:
        """Requeue message for retry."""
        await self.outbox_service.create_event(
            aggregate_id=message.id,
            aggregate_type="message",
            event_type="message.retry",
            payload={
                "message_id": str(message.id),
                "tenant_id": str(message.tenant_id),
                "retry_count": message.retry_count
            },
            tenant_id=message.tenant_id,
            scheduled_at=datetime.utcnow() + timedelta(seconds=delay_seconds)
        )
    
    def _calculate_retry_delay(self, retry_count: int) -> int:
        """Calculate exponential backoff delay."""
        # 2^n seconds, max 3600 (1 hour)
        return min(2 ** retry_count, 3600)

    async def list_messages(
        self,
        tenant_id: UUID,
        channel_id: UUID,
        skip: int = 0,
        limit: int = 100,
        direction: Optional[MessageDirection] = None
    ) -> List[Message]:
        """List messages for a channel."""
        return await self.message_repo.list_by_channel(
            channel_id=channel_id,
            tenant_id=tenant_id,
            limit=limit
        )

    async def count_messages(
        self,
        tenant_id: UUID,
        channel_id: Optional[UUID] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> int:
        """Count messages with filters."""
        try:
            conditions = ["tenant_id = :tenant_id"]
            params: Dict[str, Any] = {"tenant_id": str(tenant_id)}
            
            if channel_id:
                conditions.append("channel_id = :channel_id")
                params["channel_id"] = str(channel_id)
            
            if direction:
                conditions.append("direction = :direction")
                params["direction"] = direction
            
            if status:
                conditions.append("status = :status")
                params["status"] = status
            
            if from_date:
                conditions.append("created_at >= :from_date")
                params["from_date"] = from_date
            
            if to_date:
                conditions.append("created_at <= :to_date")
                params["to_date"] = to_date
            
            query = text(f"""
                SELECT COUNT(*) as count
                FROM messaging.messages
                WHERE {' AND '.join(conditions)}
            """)
            
            result = await self.session.execute(query, params)
            row = result.fetchone()
            
            return int(row.count) if row and row.count is not None else 0
            
        except Exception as e:
            logger.error(f"Failed to count messages: {e}")
            raise

    async def get_conversation(
        self,
        tenant_id: UUID,
        phone_number: str,
        channel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> Optional[Dict[str, Any]]:
        """Get conversation thread with a phone number."""
        try:
            conditions = [
                "tenant_id = :tenant_id",
                "(from_number = :phone OR to_number = :phone)"
            ]
            params: Dict[str, Any] = {
                "tenant_id": str(tenant_id),
                "phone": phone_number,
                "limit": limit
            }
            
            if channel_id:
                conditions.append("channel_id = :channel_id")
                params["channel_id"] = str(channel_id)
            
            query = text(f"""
                SELECT 
                    id, tenant_id, channel_id, direction, message_type,
                    from_number, to_number, content, media_url, template_id,
                    template_variables, whatsapp_message_id, status,
                    error_code, error_message, metadata, retry_count,
                    max_retries, created_at, updated_at, sent_at,
                    delivered_at, read_at
                FROM messaging.messages
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            
            result = await self.session.execute(query, params)
            
            messages: List[Message] = []
            last_message_at: Optional[datetime] = None
            unread_count = 0
            
            for row in result:
                # Convert row to Message entity
                msg = Message(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    channel_id=row.channel_id,
                    direction=MessageDirection(row.direction),
                    message_type=MessageType(row.message_type),
                    from_number=row.from_number,
                    to_number=row.to_number,
                    content=row.content,
                    media_url=row.media_url,
                    template_id=row.template_id,
                    template_variables=row.template_variables,
                    whatsapp_message_id=row.whatsapp_message_id,
                    status=MessageStatus(row.status),
                    error_code=row.error_code,
                    error_message=row.error_message,
                    metadata=row.metadata,
                    retry_count=row.retry_count or 0,
                    max_retries=row.max_retries or 3,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    sent_at=row.sent_at,
                    delivered_at=row.delivered_at,
                    read_at=row.read_at
                )
                messages.append(msg)
                
                if not last_message_at:
                    last_message_at = msg.created_at
                
                if msg.direction == MessageDirection.INBOUND and msg.status != MessageStatus.READ:
                    unread_count += 1
            
            if not messages:
                return None
            
            return {
                "phone_number": phone_number,
                "messages": messages,
                "last_message_at": last_message_at,
                "total_messages": len(messages),
                "unread_count": unread_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
            raise

    async def retry_message(
        self,
        message_id: UUID,
        tenant_id: UUID
    ) -> Optional[Message]:
        """Retry sending a failed message."""
        try:
            # Get message
            message = await self.message_repo.get_by_id(message_id, tenant_id)
            
            if not message:
                return None
            
            if message.status != MessageStatus.FAILED:
                raise ValueError("Only failed messages can be retried")
            
            if not message.can_retry():
                raise ValueError(f"Message has exceeded maximum retry count ({message.max_retries})")
            
            # Reset status to queued
            message.status = MessageStatus.QUEUED
            await self.message_repo.update(message)
            
            # Queue for processing
            await self.outbox_service.create_event(
                aggregate_id=message.id,
                aggregate_type="message",
                event_type="message.retry",
                payload={
                    "message_id": str(message.id),
                    "tenant_id": str(tenant_id),
                    "retry_count": message.retry_count + 1
                },
                tenant_id=tenant_id
            )
            
            logger.info(f"Message {message_id} queued for retry")
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to retry message: {e}")
            raise

    async def send_bulk_messages(
        self,
        tenant_id: UUID,
        channel_id: UUID,
        recipients: List[str],
        content: Optional[str] = None,
        template_name: Optional[str] = None,
        template_variables_list: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, int]:
        """Send messages to multiple recipients."""
        try:
            queued = 0
            failed = 0
            
            for i, recipient in enumerate(recipients):
                try:
                    # Get variables for this recipient
                    variables = None
                    if template_variables_list and i < len(template_variables_list):
                        variables = template_variables_list[i]
                    
                    # Send message
                    await self.send_message(
                        tenant_id=tenant_id,
                        channel_id=channel_id,
                        to_number=recipient,
                        content=content,
                        template_name=template_name,
                        template_variables=variables
                    )
                    
                    queued += 1
                    
                except Exception as e:
                    logger.error(f"Failed to queue message for {recipient}: {e}")
                    failed += 1
                
                # Small delay to avoid overwhelming the system
                if queued % 100 == 0:
                    await asyncio.sleep(0.1)
            
            logger.info(f"Bulk send completed: {queued} queued, {failed} failed")
            
            return {
                "queued": queued,
                "failed": failed
            }
            
        except Exception as e:
            logger.error(f"Failed to send bulk messages: {e}")
            raise

    async def get_message(
        self,
        message_id: UUID,
        tenant_id: UUID
    ) -> Optional[Message]:
        """Get a specific message."""
        return await self.message_repo.get_by_id(message_id, tenant_id)