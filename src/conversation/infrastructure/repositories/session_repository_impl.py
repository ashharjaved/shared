# Begin: src/conversation/infrastructure/repositories/session_repository_impl.py ***
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, text, update

from ...domain.entities import ConversationSession
from ...domain.value_objects import PhoneNumber, SessionStatus, JSONValue
from ...domain.repositories.session_repository import SessionRepository
from ..models import ConversationSessionORM
from ..rls import with_rls

logger = logging.getLogger(__name__)


class PostgresSessionRepository(SessionRepository):
    """
    Postgres-backed SessionRepository.
    - Uses stored procedures sp_open_session/sp_close_session.
    - Enforces RLS via with_rls() using tenant_id provided at construction.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
        roles_csv: Optional[str] = None,
    ) -> None:
        self._sf = session_factory
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._roles_csv = roles_csv

    # -------------------- mapping --------------------
    @staticmethod
    def _to_domain(row: ConversationSessionORM) -> ConversationSession:
        return ConversationSession(
            id=row.id,
            tenant_id=row.tenant_id,
            channel_id=row.channel_id,
            phone_number=PhoneNumber(row.phone_number),
            current_menu_id=row.current_menu_id,
            status=SessionStatus(row.status),  # StrEnum compatible
            expires_at=row.expires_at,
            last_activity=row.last_activity,
            message_count=row.message_count,
            context=dict(row.context_jsonb or {}),
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )

    # -------------------- operations --------------------
    async def open(self, *, channel_id: UUID, phone_number: str) -> ConversationSession:
        """
        Upsert by (channel_id, phone_number), refresh TTL and set ACTIVE.
        """
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            # Call stored procedure (returns uuid)
            cur = await s.execute(
                text("SELECT sp_open_session(:cid, :ph)"),
                {"cid": str(channel_id), "ph": phone_number},
            )
            session_id = cur.scalar_one()
            # Fetch the row
            row = (
                await s.execute(select(ConversationSessionORM).where(ConversationSessionORM.id == session_id))
            ).scalars().first()
            assert row is not None, "sp_open_session returned id but row not found"
            await s.commit()
            return self._to_domain(row)

    async def get_by_channel_phone(self, *, channel_id: UUID, phone_number: str) -> Optional[ConversationSession]:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            row = (
                await s.execute(
                    select(ConversationSessionORM).where(
                        ConversationSessionORM.channel_id == channel_id,
                        ConversationSessionORM.phone_number == phone_number,
                    )
                )
            ).scalars().first()
            return self._to_domain(row) if row else None

    async def set_current_menu(self, *, session_id: UUID, menu_id: Optional[UUID]) -> None:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            await s.execute(
                update(ConversationSessionORM)
                .where(ConversationSessionORM.id == session_id)
                .values(current_menu_id=menu_id, updated_at=sa.text("now()"))
            )
            await s.commit()

    async def bump_message_count(self, *, session_id: UUID) -> None:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            await s.execute(
                text(
                    """
                    UPDATE conversation_sessions
                       SET message_count = message_count + 1,
                           last_activity = now(),
                           updated_at = now()
                     WHERE id = :sid
                    """
                ),
                {"sid": str(session_id)},
            )
            await s.commit()

    async def save_context(self, *, session_id: UUID, context: dict[str, JSONValue]) -> None:
        """
        Merge context (jsonb ||) to avoid read/modify/write races.
        """
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            await s.execute(
                text(
                    """
                    UPDATE conversation_sessions
                       SET context_jsonb = COALESCE(context_jsonb, '{}'::jsonb) || :delta::jsonb,
                           updated_at = now()
                     WHERE id = :sid
                    """
                ),
                {"sid": str(session_id), "delta": sa.text(":payload")},
            )
            # NOTE: SQLAlchemy binds JSON via parameters; we must pass a real dict.
            # Using separate execute to bind the json payload safely:
            await s.execute(
                text(
                    """
                    UPDATE conversation_sessions
                       SET context_jsonb = COALESCE(context_jsonb, '{}'::jsonb) || :payload::jsonb,
                           updated_at = now()
                     WHERE id = :sid
                    """
                ),
                {"sid": str(session_id), "payload": context},
            )
            await s.commit()

    async def close(self, *, session_id: UUID) -> None:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            await s.execute(text("SELECT sp_close_session(:sid)"), {"sid": str(session_id)})
            await s.commit()
# End: src/conversation/infrastructure/repositories/session_repository_impl.py ***
