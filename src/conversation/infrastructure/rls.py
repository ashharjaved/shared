# Begin: src/conversation/infrastructure/rls.py ***
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

@asynccontextmanager
async def with_rls(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: Optional[UUID] = None,
    roles_csv: Optional[str] = None,
) -> AsyncIterator[AsyncSession]:
    """
    Enforce Postgres RLS by setting app-specific GUCs inside a single transaction.

    Usage:
        async with async_session_factory() as s:
            async with with_rls(s, tenant_id=tid, user_id=uid, roles_csv=roles):
                await s.execute(...)
                await s.commit()  # optional; context manages a begin/commit block
    """
    async with session.begin():
        await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": str(tenant_id)},)
                                   
        if user_id is not None:
            await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)},)
        if roles_csv:
            await session.execute(text("SELECT set_config('app.roles', :r, true)"), {"r": str(roles_csv)},)
        yield session
# End: src/conversation/infrastructure/rls.py ***
