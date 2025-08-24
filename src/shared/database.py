from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from src.config import get_settings

logger = logging.getLogger("app.db")

_engine = create_async_engine(str(get_settings().DATABASE_URL), echo=False, future=True, pool_pre_ping=True)
SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

tenant_ctx: ContextVar[str | None] = ContextVar("tenant_ctx", default=None)
user_ctx: ContextVar[str | None] = ContextVar("user_ctx", default=None)
roles_ctx: ContextVar[str | None] = ContextVar("roles_ctx", default=None)


async def set_rls_gucs(session: AsyncSession, tenant_id: str | None, user_id: str | None, roles: str | None) -> None:
    # SET LOCAL requires a transaction scope; caller must be inside session.begin()
    if tenant_id:
        await session.execute(text("SET LOCAL app.jwt_tenant = :t"), {"t": tenant_id})
    if user_id:
        await session.execute(text("SET LOCAL app.user_id = :u"), {"u": user_id})
    if roles:
        await session.execute(text("SET LOCAL app.roles = :r"), {"r": roles})


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        async with session.begin():
            await set_rls_gucs(
                session,
                tenant_ctx.get(),
                user_ctx.get(),
                roles_ctx.get(),
            )
            yield session  # commits on context exit
