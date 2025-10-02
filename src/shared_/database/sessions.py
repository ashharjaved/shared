"""
sessions.py — Tenant-aware database sessions with RLS (Row-Level Security).

This module provides async context managers for obtaining SQLAlchemy sessions
that automatically enforce the project's RLS & GUC contract.

- Usage:
    async with get_session_with_rls(tenant_id, user_id, roles) as session:
        ...  # safe DB operations scoped to tenant
    async with session_from_ctxvars(require_tenant=True) as session:
        ...  # tenant auto-resolved from request ctxvars
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared_.database.uow import AsyncUoW
from src.shared_.database.types import TenantContext
from src.shared_.database.rls import apply_rls_locals, verify_rls_context, tenant_context_from_ctxvars


@asynccontextmanager
async def get_session_with_rls(
    tenant_id: str,
    user_id: Optional[str] = None,
    roles: Optional[list[str]] = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession with explicit tenant/user/roles context applied.

    This sets Postgres GUCs (`app.jwt_tenant`, `app.user_id`, `app.roles`)
    via `SET LOCAL` so that all RLS policies are enforced.

    Args:
        tenant_id: UUID of the tenant (string form).
        user_id: Optional user UUID (string form).
        roles: Optional list of role names (strings).

    Yields:
        AsyncSession with an open transaction, RLS enforced.

    Raises:
        RlsNotSetError: If RLS context verification fails.
        Exception: Any DB error is propagated after rollback.

    Notes:
        - Must always be used for tenant-scoped DB operations.
        - Ensures no cross-tenant data leaks.
    """
    from src.shared_.database.database import get_async_session   
    async def _sf():
        async with get_async_session() as s:
            return s
    ctx = TenantContext.from_maybe(tenant_id, user_id, roles)
    async with AsyncUoW(_sf, context=ctx, require_tenant=True) as uow:
        yield uow.require_session()

    

@asynccontextmanager
async def session_from_ctxvars(require_tenant: bool = True) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession using tenant/user/roles automatically from ctxvars.

    Convenience wrapper for request-handling code, where tenant context
    is propagated through request-scoped ctxvars.

    Args:
        require_tenant: If True (default), raise error if no tenant is found.

    Yields:
        AsyncSession with RLS context applied (if tenant exists).

    Raises:
        RuntimeError: If require_tenant=True but tenant ctx is missing.
        RlsNotSetError: If RLS verification fails.
    """
    from src.shared_.database.database import get_async_session
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