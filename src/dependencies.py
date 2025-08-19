from __future__ import annotations

from typing import AsyncGenerator, Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import async_session_factory
from src.shared.security import get_principal, Principal


async def get_tenant_context(
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
    principal: Optional[Principal] = Depends(get_principal),
) -> Optional[str]:
    """Resolve the tenant identifier for the current request."""
    # Prefer tenant from JWT; otherwise use header (bootstrap).
    return Principal["tenant_id"] if Principal else x_tenant_id


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Canonical DB session dependency (async)."""
    async with async_session_factory() as session:
        yield session

