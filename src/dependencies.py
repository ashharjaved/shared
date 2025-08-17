from __future__ import annotations
from typing import Optional
from fastapi import Header
from .shared.security import get_principal
from .identity.domain.entities import Principal
from sqlalchemy.ext.asyncio import AsyncSession
from .shared.database import async_session_factory

async def get_tenant_context(x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
                             principal: Optional[Principal] = await get_principal()) -> Optional[str]:  # type: ignore
    # Prefer tenant from JWT; otherwise use header (bootstrap).
    return principal.tenant_id if principal else x_tenant_id

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Canonical DB session dependency (async)."""
    async with async_session_factory() as session:
        yield session