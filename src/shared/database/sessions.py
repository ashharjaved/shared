from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.engine import get_session_factory
from src.shared.database.types import TenantContext
from src.shared.database.rls import apply_rls_locals, verify_rls_context, tenant_context_from_ctxvars


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Plain session (no implicit RLS). Caller decides whether to apply RLS.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_with_rls(
    tenant_id: str,
    user_id: Optional[str] = None,
    roles: Optional[list[str]] = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Session with an explicit transaction that sets GUCs via SET LOCAL.
    """
    async with get_async_session() as session:
        async with session.begin():
            ctx = TenantContext.from_maybe(tenant_id, user_id, roles)
            await apply_rls_locals(session, ctx)
            await verify_rls_context(session)
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_from_ctxvars(require_tenant: bool = True) -> AsyncGenerator[AsyncSession, None]:
    """
    Convenience: create a session and, if tenant information exists in ctxvars,
    apply it automatically. If require_tenant=True, assert tenant is present.
    """
    async with get_async_session() as session:
        async with session.begin():
            ctx = tenant_context_from_ctxvars()
            if require_tenant and (ctx is None or not ctx.tenant_id):
                # Let your global 403 handler map to proper response.
                raise RuntimeError("Tenant context not set")
            if ctx and ctx.tenant_id:
                await apply_rls_locals(session, ctx)
                await verify_rls_context(session)
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
