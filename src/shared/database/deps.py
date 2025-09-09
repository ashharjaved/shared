from __future__ import annotations

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.sessions import get_async_session, session_from_ctxvars


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI: plain DB session (no RLS). Use only for admin/maintenance endpoints.
    """
    async with get_async_session() as session:
        yield session


async def get_tenant_scoped_db(require_tenant: bool = True) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI: DB session that reads ctxvars and applies tenant RLS automatically.
    """
    async with session_from_ctxvars(require_tenant=require_tenant) as session:
        yield session
