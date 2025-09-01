from __future__ import annotations

import secrets
from typing import List, Optional
from uuid import UUID

from src.messaging.domain.entities.channel import Channel
from src.messaging.domain.repositories.channel_repository import ChannelRepository


class ChannelService:
    """
    Orchestrates channel lifecycle. Secrets must remain encrypted-at-rest by infra repo.
    """

    def __init__(self, channel_repo: ChannelRepository) -> None:
        self._channels = channel_repo

    async def register_channel(
        self,
        *,
        name: str,
        phone_number_id: str,
        business_phone: str,
        access_token_plain: str,
        is_active: bool = True,
        rate_limit_per_second: Optional[int] = None,
        monthly_message_limit: Optional[int] = None,
        tenant_id: UUID,
    ) -> Channel:
        # Generate a fresh webhook verification token for the channel
        webhook_token = secrets.token_urlsafe(24)

        channel = Channel(
            id=UUID(int=0),  # DB will generate
            tenant_id=tenant_id,
            name=name,
            phone_number_id=phone_number_id,
            business_phone=business_phone,
            token=access_token_plain,
            webhook_token=webhook_token,
            rate_limit_per_second=rate_limit_per_second,
            monthly_message_limit=monthly_message_limit,
            is_active=is_active,
        )
        return await self._channels.create(channel)

    async def list_channels(self) -> List[Channel]:
        return await self._channels.list()

    async def get(self, channel_id: UUID) -> Optional[Channel]:
        return await self._channels.find_by_id(channel_id)

    async def rotate_webhook_token(self, channel_id: UUID) -> Channel:
        ch = await self._channels.find_by_id(channel_id)
        if not ch:
            raise ValueError("channel_not_found")
        new_token = secrets.token_urlsafe(24)
        # Persist rotation by creating an updated entity; let Infra handle partial update.
        updated = Channel(
            id=ch.id,
            tenant_id=ch.tenant_id,
            name=ch.name,
            phone_number_id=ch.phone_number_id,
            business_phone=ch.business_phone,
            token=ch.token,
            webhook_token=new_token,
            rate_limit_per_second=ch.rate_limit_per_second,
            monthly_message_limit=ch.monthly_message_limit,
            is_active=ch.is_active,
            created_at=ch.created_at,
            updated_at=ch.updated_at,
        )
        # Reuse create for simplicity if repo implements upsert; otherwise, add a dedicated update method.
        # If your repo does not support upsert via create(), add update() to the interface and call it.
        return await self._channels.create(updated)
