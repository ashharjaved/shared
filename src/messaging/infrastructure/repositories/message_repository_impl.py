from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.messaging.domain.entities.message import (
    Message,
    MessageDirection,
    MessageStatus,
    PhoneNumber,
)
from src.messaging.domain.repositories.message_repository import MessageRepository
from src.messaging.infrastructure.models.message_model import MessageModel

from src.shared.exceptions import DomainError, DomainConflictError, RateLimitedError  # adjust names if needed
from src.messaging.domain.types import GetChannelLimits

class PostgresMessageRepository(MessageRepository):
    """
    RLS-aware implementation.
    Wraps DB procs: sp_send_message, sp_update_message_status.

    Optional Redis integration:
      - per-second rate limiting
      - monthly usage counter
      - small cache for recent conversations
    Channel limits are provided via get_channel_limits callback.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_id: UUID,
        *,
        redis: Optional[Redis] = None,
        get_channel_limits: GetChannelLimits,
    ) -> None:
        self._sf = session_factory
        self._tenant_id = tenant_id
        self._redis = redis
        self._get_channel_limits = get_channel_limits

    async def _set_tenant(self, session: AsyncSession) -> None:
        await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": str(self._tenant_id)})

    # ------------------------- Redis Helpers -------------------------

    async def _check_rate_limits(self, channel_id: UUID) -> None:
        if not self._redis:
            return
        per_sec, monthly = await self._get_channel_limits(channel_id)
        now = datetime.utcnow()

        if per_sec:
            sec_key = f"rl:{self._tenant_id}:{channel_id}:{int(now.timestamp())}"
            v = await self._redis.incr(sec_key)
            if v == 1:
                await self._redis.expire(sec_key, 1)
            if v > per_sec:
                raise RateLimitedError("messages_per_second_limit_exceeded")

        if monthly:
            ym = f"{now.year:04d}{now.month:02d}"
            usage_key = f"usage:{self._tenant_id}:{channel_id}:{ym}"
            current = await self._redis.get(usage_key)
            current_i = int(current) if current is not None else 0
            if current_i >= monthly:
                raise DomainConflictError("monthly_message_limit_exceeded")

    async def _bump_monthly_usage(self, channel_id: UUID) -> None:
        if not self._redis:
            return
        now = datetime.utcnow()
        ym = f"{now.year:04d}{now.month:02d}"
        usage_key = f"usage:{self._tenant_id}:{channel_id}:{ym}"
        v = await self._redis.incr(usage_key)
        # expire slightly past month end (e.g., 40 days)
        if v == 1:
            await self._redis.expire(usage_key, 40 * 24 * 3600)

    # ------------------------- Mapping -------------------------

    def _row_to_domain(self, row: MessageModel) -> Message:
        # Note: DB stores enums in uppercase; domain enum maps by value.
        return Message(
            id=row.id,
            tenant_id=row.tenant_id,
            channel_id=row.channel_id,
            from_phone=PhoneNumber(row.from_phone),
            to_phone=PhoneNumber(row.to_phone),
            content=row.content_jsonb,
            message_type=row.message_type,  # keep string
            direction=MessageDirection(row.direction),
            status=MessageStatus(row.status),
            whatsapp_message_id=row.whatsapp_message_id,
            error_code=row.error_code,
            retry_count=row.retry_count,
            created_at=row.created_at,
            status_updated_at=row.status_updated_at,
            delivered_at=row.delivered_at,
        )

    # ------------------------- Interface -------------------------

    async def queue_message(self, message: Message, *, idempotency_key: Optional[str] = None) -> Message:
        """
        Leverages DB function sp_send_message(channel_id, to_phone, message_type, content_json, idempotency_key)
        DB will:
          - validate/legalize content
          - compute content_hash
          - insert row (status=QUEUED, direction=OUTBOUND)
          - write outbox event
          - enforce idempotency (via ensure_idempotency/unique key)
        """
        # Rate limiting (best-effort, before queuing)
        await self._check_rate_limits(message.channel_id)

        async with self._sf() as session:
            async with session.begin():
                await self._set_tenant(session)
                payload_json = json.dumps(message.content, separators=(",", ":"), ensure_ascii=False)

                # sp_send_message returns UUID
                res = await session.execute(
                    text(
                        "SELECT sp_send_message(:cid, :to_phone, :msg_type, :payload_json, :idem_key)"
                    ),
                    {
                        "cid": str(message.channel_id),
                        "to_phone": str(message.to_phone),
                        "msg_type": message.message_type.upper(),
                        "payload_json": payload_json,
                        "idem_key": idempotency_key,
                    },
                )
                row = res.first()
                if not row or not row[0]:
                    # DB treat duplicates as no-op and may return NULL; convert to conflict
                    raise DomainConflictError("idempotency_conflict")

                new_id: UUID = row[0]

            # Fetch the inserted row to hydrate domain object
            await self._set_tenant(session)
            db_row = await session.get(MessageModel, new_id)
            if not db_row:
                raise DomainError("message_not_found_after_insert")

        # Increment monthly usage only after success
        await self._bump_monthly_usage(message.channel_id)
        return self._row_to_domain(db_row)

    async def update_status(self, message_id: UUID, new_status: MessageStatus) -> Message:
        async with self._sf() as session:
            async with session.begin():
                await self._set_tenant(session)
                await session.execute(
                    text("CALL sp_update_message_status(:mid, :new_status)"),
                    {"mid": str(message_id), "new_status": new_status.value},
                )

            await self._set_tenant(session)
            row = await session.get(MessageModel, message_id)
            if not row:
                raise DomainError("message_not_found")
            return self._row_to_domain(row)

    async def find_by_id(self, message_id: UUID) -> Optional[Message]:
        async with self._sf() as session:
            await self._set_tenant(session)
            row = await session.get(MessageModel, message_id)
            return self._row_to_domain(row) if row else None

    async def get_recent_conversation(
        self, channel_id: UUID, peer_phone: PhoneNumber, *, limit: int = 50
    ) -> List[Message]:
        cache_key = None
        if self._redis:
            cache_key = f"conv:{self._tenant_id}:{channel_id}:{peer_phone}"
            cached = await self._redis.get(cache_key)
            if cached:
                items = json.loads(cached)
                return [
                    Message(
                        id=UUID(x["id"]),
                        tenant_id=UUID(x["tenant_id"]),
                        channel_id=UUID(x["channel_id"]),
                        from_phone=PhoneNumber(x["from_phone"]),
                        to_phone=PhoneNumber(x["to_phone"]),
                        content=x["content"],
                        message_type=x["message_type"],
                        direction=MessageDirection(x["direction"]),
                        status=MessageStatus(x["status"]),
                        whatsapp_message_id=x.get("whatsapp_message_id"),
                        error_code=x.get("error_code"),
                        retry_count=x.get("retry_count", 0),
                        created_at=datetime.fromisoformat(x["created_at"]),
                        status_updated_at=datetime.fromisoformat(x["status_updated_at"]),
                        delivered_at=datetime.fromisoformat(x["delivered_at"]) if x.get("delivered_at") else None,
                    )
                    for x in items
                ]

        async with self._sf() as session:
            await self._set_tenant(session)
            stmt: Select = (
                select(MessageModel)
                .where(
                    MessageModel.channel_id == channel_id,
                    (MessageModel.from_phone == str(peer_phone)) | (MessageModel.to_phone == str(peer_phone)),
                )
                .order_by(MessageModel.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            messages = [self._row_to_domain(r) for r in rows]

        if self._redis and cache_key:
            # Short-lived cache (15 seconds) to ease UI polling
            serial = [
                {
                    "id": str(m.id),
                    "tenant_id": str(m.tenant_id),
                    "channel_id": str(m.channel_id),
                    "from_phone": str(m.from_phone),
                    "to_phone": str(m.to_phone),
                    "content": m.content,
                    "message_type": m.message_type,
                    "direction": m.direction.value,
                    "status": m.status.value,
                    "whatsapp_message_id": m.whatsapp_message_id,
                    "error_code": m.error_code,
                    "retry_count": m.retry_count,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "status_updated_at": m.status_updated_at.isoformat() if m.status_updated_at else None,
                    "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
                }
                for m in messages
            ]
            await self._redis.set(cache_key, json.dumps(serial, ensure_ascii=False), ex=15)

        return messages