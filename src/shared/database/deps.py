from __future__ import annotations

from typing import AsyncGenerator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.http.public_paths import is_public_path
from src.shared.database.database import get_async_session
from src.shared.database.sessions import session_from_ctxvars


async def get_db_dependency() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI: plain DB session (no RLS). Use only for admin/maintenance endpoints.
    """
    async with get_async_session() as session:
        yield session

async def get_tenant_scoped_db(request: Request):
    # Public endpoints (favicon/docs/health/webhook/auth) should not require tenant
    require_tenant = not is_public_path(request.url.path)
    async with session_from_ctxvars(require_tenant=require_tenant) as session:
        yield session