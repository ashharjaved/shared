"""Channel management service."""

import logging
from typing import Any, Dict, List, Optional
import uuid
import secrets

from uuid import UUID

from src.messaging.infrastructure.events.event_bus import EventBus
from src.messaging.domain.entities.channel import Channel, ChannelStatus
from src.messaging.domain.interfaces.repositories import ChannelRepository
from messaging.domain.protocols.external_services import WhatsAppClient, EncryptionService, WhatsAppMessageRequest
from src.messaging.domain.events.message_events import ChannelActivated
#from src.shared.infrastructure.events import EventBus

logger = logging.getLogger(__name__)


class ChannelService:
    """Service for managing WhatsApp channels."""
    
    def __init__(
        self,
        session: AsyncSession,
        channel_repo: ChannelRepository,
        whatsapp_client: WhatsAppClient,
        encryption: EncryptionService,
        event_bus: EventBus
    ):
        self.session = session
        self.channel_repo = channel_repo
        self.whatsapp_client = whatsapp_client
        self.encryption = encryption
        self.event_bus = event_bus
    
    async def create_channel(
        self,
        tenant_id: uuid.UUID,
        name: str,
        phone_number_id: str,
        business_phone: str,
        access_token: str,
        rate_limit: int = 80,
        monthly_limit: Optional[int] = None
    ) -> Channel:
        """Create and register a new WhatsApp channel."""
        try:
            # Validate by sending test message
            test_response = await self.whatsapp_client.send_message(
                phone_number_id,
                access_token,
                WhatsAppMessageRequest(
                    to=business_phone,
                    type="text",
                    text="Channel verification successful"
                )
            )
            
            if not test_response.success:
                raise ValueError(f"Channel verification failed: {test_response.error_message}")
            
            # Generate webhook verify token
            webhook_token = secrets.token_urlsafe(32)
            
            # Create channel entity
            channel = Channel(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                phone_number_id=phone_number_id,
                business_phone=business_phone,
                access_token=access_token,  # Will be encrypted in repository
                status=ChannelStatus.ACTIVE,
                rate_limit_per_second=rate_limit,
                monthly_message_limit=monthly_limit,
                webhook_verify_token=webhook_token
            )
            
            # Save channel
            channel = await self.channel_repo.create(channel)
            
            # Publish event
            event = ChannelActivated(
                event_id=uuid.uuid4(),
                aggregate_id=channel.id,
                tenant_id=tenant_id,
                occurred_at=channel.created_at,
                channel_name=name,
                phone_number=business_phone
            )
            await self.event_bus.publish(event)
            
            logger.info(f"Channel {channel.id} created for tenant {tenant_id}")
            
            return channel
            
        except Exception as e:
            logger.error(f"Failed to create channel: {e}")
            raise
    
    async def get_channel(
        self,
        channel_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> Optional[Channel]:
        """Get channel by ID."""
        return await self.channel_repo.get_by_id(channel_id, tenant_id)
    
    # Add to src/messaging/application/services/channel_service.py

    async def get_channel_stats(
        self,
        channel_id: UUID,
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """Get channel statistics."""
        try:
            # Use the query handler
            from src.messaging.application.queries.get_channel_stats_query import (
                GetChannelStatsQuery, GetChannelStatsQueryHandler
            )
            
            query = GetChannelStatsQuery(
                tenant_id=tenant_id,
                channel_id=channel_id,
                period="today"
            )
            
            handler = GetChannelStatsQueryHandler(self.session)
            stats = await handler.handle(query)
            
            return {
                "channel_id": channel_id,
                "messages_sent_today": stats.messages_sent,
                "messages_received_today": stats.messages_received,
                "messages_failed_today": stats.messages_failed,
                "current_month_usage": stats.current_month_usage,
                "monthly_limit": stats.monthly_limit,
                "usage_percentage": stats.usage_percentage,
                "last_message_at": stats.last_message_at
            }
            
        except Exception as e:
            logger.error(f"Failed to get channel stats: {e}")
            raise

    async def list_channels(
        self,
        tenant_id: uuid.UUID
    ) -> List[Channel]:
        """List all channels for a tenant."""
        return await self.channel_repo.list_by_tenant(tenant_id)
    
    async def update_channel(
        self,
        channel_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: Optional[str] = None,
        access_token: Optional[str] = None,
        rate_limit: Optional[int] = None,
        monthly_limit: Optional[int] = None
    ) -> Channel:
        """Update channel configuration."""
        try:
            channel = await self.channel_repo.get_by_id(channel_id, tenant_id)
            if not channel:
                raise ValueError(f"Channel {channel_id} not found")
            
            # Update fields
            if name:
                channel.name = name
            if access_token:
                # Validate new token
                test_response = await self.whatsapp_client.send_message(
                    channel.phone_number_id,
                    access_token,
                    WhatsAppMessageRequest(
                        to=channel.business_phone,
                        type="text",
                        text="Token update verification"
                    )
                )
                if test_response.success:
                    channel.access_token = access_token
                else:
                    raise ValueError(f"Token validation failed: {test_response.error_message}")
            if rate_limit:
                channel.rate_limit_per_second = rate_limit
            if monthly_limit is not None:
                channel.monthly_message_limit = monthly_limit
            
            # Save updates
            channel = await self.channel_repo.update(channel)
            
            logger.info(f"Channel {channel_id} updated")
            
            return channel
            
        except Exception as e:
            logger.error(f"Failed to update channel: {e}")
            raise
    
    async def deactivate_channel(
        self,
        channel_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> None:
        """Deactivate a channel."""
        try:
            channel = await self.channel_repo.get_by_id(channel_id, tenant_id)
            if not channel:
                raise ValueError(f"Channel {channel_id} not found")
            
            channel.deactivate()
            await self.channel_repo.update(channel)
            
            logger.info(f"Channel {channel_id} deactivated")
            
        except Exception as e:
            logger.error(f"Failed to deactivate channel: {e}")
            raise
    
    async def reset_monthly_usage(
        self,
        tenant_id: uuid.UUID
    ) -> None:
        """Reset monthly usage for all channels (called by scheduler)."""
        try:
            channels = await self.channel_repo.list_by_tenant(tenant_id)
            
            for channel in channels:
                channel.reset_monthly_usage()
                await self.channel_repo.update(channel)
            
            logger.info(f"Reset monthly usage for {len(channels)} channels")
            
        except Exception as e:
            logger.error(f"Failed to reset usage: {e}")
            raise