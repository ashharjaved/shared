from __future__ import annotations

from typing import Optional
from uuid import UUID

import debugpy
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session as _db_get_session
from typing import AsyncGenerator
from src.shared.security import get_principal, Principal


async def get_tenant_context(
    x_tenant_id: Optional[UUID] = Header(default=None, alias="X-Tenant-Id"),
    principal: Optional[Principal] = Depends(get_principal),
) -> Optional[str]:
    """
    Resolve the current tenant for this request.

    Precedence:
      1) tenant_id from authenticated JWT (set by get_principal), else
      2) X-Tenant-Id header (bootstrap / public routes)
    """
    debugpy.breakpoint()
    tenant_id = principal.tenant_id if (principal and principal.tenant_id) else x_tenant_id
    return str(tenant_id) if tenant_id is not None else None


# Convenience alias: some modules expect `get_db_session` name
async def get_db_session() -> AsyncSession:
    debugpy.breakpoint()
    """
    Backwards-compatible wrapper so existing code that depends on
    `get_db_session` keeps working. Prefer `get_session` directly.
    """
    async for s in get_session():  # type: ignore[misc]
        return s
    # Should never reach here; generator always yields exactly once.
    raise RuntimeError("Failed to acquire AsyncSession from get_session()")

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for s in _db_get_session():
        yield s