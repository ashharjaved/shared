# from __future__ import annotations

# from typing import AsyncGenerator, Optional

# from fastapi import Depends, Header
# from sqlalchemy.ext.asyncio import AsyncSession

# from src.shared.database import async_session_factory
# from src.shared.security import get_principal, Principal


# async def get_tenant_context(
#     x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
#     principal: Optional[Principal] = Depends(get_principal),
# ) -> Optional[str]:
#     """Resolve the tenant identifier for the current request."""
#     # Prefer tenant from JWT; otherwise use header (bootstrap).
#     return Principal["tenant_id"] if Principal else x_tenant_id


# async def get_session() -> AsyncGenerator[AsyncSession, None]:
#     """Canonical DB session dependency (async)."""
#     async with async_session_factory() as session:
#         yield session

###############-------------------------------------------------------------------
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

# Re-export the canonical async DB session dependency for FastAPI routes
from src.shared.database import get_session as get_session

# Auth / principal (dict-like) from shared.security
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
    tenant_id = principal.tenant_id if (principal and principal.tenant_id) else x_tenant_id
    return str(tenant_id) if tenant_id is not None else None


# Convenience alias: some modules expect `get_db_session` name
async def get_db_session() -> AsyncSession:
    """
    Backwards-compatible wrapper so existing code that depends on
    `get_db_session` keeps working. Prefer `get_session` directly.
    """
    async for s in get_session():  # type: ignore[misc]
        return s
    # Should never reach here; generator always yields exactly once.
    raise RuntimeError("Failed to acquire AsyncSession from get_session()")
