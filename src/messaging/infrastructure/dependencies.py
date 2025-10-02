"""Dependency injection for messaging module."""

from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.shared_.database.deps import get_tenant_scoped_db
from src.messaging.infrastructure.adapters.whatsapp_adapter import WhatsAppAPIAdapter
from messaging.infrastructure.persistence.adapter.encryption_adapter import EncryptionAdapter
from messaging.infrastructure.persistence.adapter.google_speech_adapter import GoogleSpeechAdapter
from src.messaging.infrastructure.repositories.channel_repository_impl import ChannelRepositoryImpl
from src.messaging.infrastructure.repositories.message_repository_impl import MessageRepositoryImpl
from src.messaging.infrastructure.repositories.template_repository_impl import TemplateRepositoryImpl
from src.messaging.infrastructure.rate_limiter.token_bucket import TokenBucketRateLimiter
from src.messaging.infrastructure.cache.redis_cache import MessagingCache
from src.messaging.infrastructure.events.event_bus import EventBus
from src.messaging.infrastructure.outbox.outbox_service import OutboxService
from src.messaging.application.services.webhook_service import WebhookService
from src.messaging.application.services.message_service import MessageService
from src.messaging.application.services.channel_service import ChannelService
from src.messaging.application.services.template_service import TemplateService


# Redis client singleton
_redis_client = None

async def get_redis() -> redis.Redis:
    """Get Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = await redis.from_url(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_client


# Service dependencies
async def get_webhook_service(
    session: AsyncSession = Depends(get_tenant_scoped_db),
    redis: redis.Redis = Depends(get_redis)
) -> WebhookService:
    """Get webhook service."""
    message_repo = MessageRepositoryImpl(session)
    channel_repo = ChannelRepositoryImpl(session, EncryptionAdapter())
    whatsapp_client = WhatsAppAPIAdapter()
    speech_client = GoogleSpeechAdapter()
    cache = MessagingCache(redis)
    event_bus = EventBus(redis)
    
    return WebhookService(
        message_repo=message_repo,
        channel_repo=channel_repo,
        whatsapp_client=whatsapp_client,
        speech_client=speech_client,
        redis_cache=cache,
        event_bus=event_bus
    )


async def get_message_service(
    session: AsyncSession = Depends(get_tenant_scoped_db),  # ✅ FIXED
    redis: redis.Redis = Depends(get_redis)
) -> MessageService:
    """Get message service."""
    message_repo = MessageRepositoryImpl(session)
    channel_repo = ChannelRepositoryImpl(session, EncryptionAdapter())
    template_repo = TemplateRepositoryImpl(session)
    whatsapp_client = WhatsAppAPIAdapter()
    rate_limiter = TokenBucketRateLimiter(redis)
    cache = MessagingCache(redis)
    outbox = OutboxService(session)
    
    return MessageService(
        message_repo=message_repo,
        channel_repo=channel_repo,
        template_repo=template_repo,
        whatsapp_client=whatsapp_client,
        rate_limiter=rate_limiter,
        redis_cache=cache,
        outbox=outbox
    )


async def get_channel_service(
    session: AsyncSession = Depends(get_tenant_scoped_db)  # ✅ FIXED
) -> ChannelService:
    """Get channel service."""
    channel_repo = ChannelRepositoryImpl(session, EncryptionAdapter())
    whatsapp_client = WhatsAppAPIAdapter()
    encryption = EncryptionAdapter()
    
    return ChannelService(
        channel_repo=channel_repo,
        whatsapp_client=whatsapp_client,
        encryption=encryption,
        session=session
    )


async def get_template_service(
    session: AsyncSession = Depends(get_tenant_scoped_db),
    redis: redis.Redis = Depends(get_redis)
) -> TemplateService:
    """Get template service."""
    template_repo = TemplateRepositoryImpl(session)
    channel_repo = ChannelRepositoryImpl(session, EncryptionAdapter())
    whatsapp_client = WhatsAppAPIAdapter()
    event_bus = EventBus(redis)
    
    return TemplateService(
        template_repo=template_repo,
        channel_repo=channel_repo,
        whatsapp_client=whatsapp_client,
        event_bus=event_bus
    )