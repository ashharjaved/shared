from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import AsyncIterator, Optional

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


async def set_rls_gucs(session, *, tenant_id: str, user_id: Optional[str] = None, role: Optional[str] = None) -> None:
    """
    Set per-request RLS context. Uses set_config(..., true) to scope values to the current transaction.
    Must be called *before* any tenant-scoped query.
    """
    # tenant (REQUIRED)
    await session.execute(
        text("SELECT set_config('app.jwt_tenant', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )
    # user (OPTIONAL)
    if user_id:
        await session.execute(
            text("SELECT set_config('app.jwt_user', :user_id, true)"),
            {"user_id": user_id},
        )
    # role (OPTIONAL)
    if role:
        await session.execute(
            text("SELECT set_config('app.jwt_role', :role, true)"),
            {"role": role},
        )


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    Yields a transaction-scoped AsyncSession and sets the RLS GUCs
    from the per-request ContextVars (tenant_ctx, user_ctx, roles_ctx).
    Must be used by all routes that touch the DB.
    """
    async with SessionLocal() as session:
        # open a transaction so set_config(..., true) is scoped correctly
        async with session.begin():
            await set_rls_gucs(
                session,
                tenant_id=tenant_ctx.get() or "",   # pass empty if not set; safe for platform-scoped tables
                user_id=user_ctx.get() or None,
                role=roles_ctx.get() or None,
            )
        # after GUCs are set, yield the session for repositories
        yield session
