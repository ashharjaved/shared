from __future__ import annotations

from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.messaging.domain.entities.channel import Channel
from src.messaging.domain.repositories.channel_repository import ChannelRepository
from src.messaging.infrastructure.models.channel_model import WhatsAppChannelModel

class PostgresChannelRepository(ChannelRepository):
    """
    Postgres implementation with:
      - RLS via SET LOCAL app.jwt_tenant
      - Encryption-at-rest for access_token/webhook_token via injected callables
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_id: UUID,
        *,
        encrypt: Callable[[str], str],
        decrypt: Callable[[str], str],
    ) -> None:
        self._sf = session_factory
        self._tenant_id = tenant_id
        self._encrypt = encrypt
        self._decrypt = decrypt

    async def _set_tenant(self, session: AsyncSession) -> None:
        await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": str(self._tenant_id)})

    def _to_domain(self, row: WhatsAppChannelModel) -> Channel:
        return Channel(
            id=row.id,
            tenant_id=row.tenant_id,
            #name=getattr(row, "name", None) or f"WA-{row.phone_number_id}",  # tolerate missing name in SQL schema
            phone_number_id=row.phone_number_id,
            business_phone=row.business_phone,
            token=None,
            webhook_token=None,
            webhook_url=row.webhook_url,
            #access_token=self._decrypt(row.access_token),
            #webhook_token=self._decrypt(row.webhook_token),
            rate_limit_per_second=row.rate_limit_per_second,
            monthly_message_limit=row.monthly_message_limit,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create(self, channel: Channel) -> Channel:
        async with self._sf() as session:
            async with session.begin():
                await self._set_tenant(session)
                model = WhatsAppChannelModel(
                    tenant_id=self._tenant_id,
                    phone_number_id=channel.phone_number_id,
                    business_phone=channel.business_phone,
                    access_token=self._encrypt(channel.token),
                    webhook_url = channel.webhook_url,
                    webhook_token=self._encrypt(channel.webhook_token),
                    rate_limit_per_second=channel.rate_limit_per_second or 10,
                    monthly_message_limit=channel.monthly_message_limit or 100000,
                    is_active=channel.is_active,
                )
                session.add(model)
            await session.refresh(model)
            return self._to_domain(model)

    async def list(self) -> List[Channel]:
        async with self._sf() as session:
            await self._set_tenant(session)
            rows = (await session.execute(select(WhatsAppChannelModel))).scalars().all()
            return [self._to_domain(r) for r in rows]

    async def find_by_id(self, channel_id: UUID) -> Optional[Channel]:
        async with self._sf() as session:
            await self._set_tenant(session)
            row = await session.get(WhatsAppChannelModel, channel_id)
            if not row:
                return None
            return self._to_domain(row)
