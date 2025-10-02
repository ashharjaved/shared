"""
rls.py — Helpers for Postgres Row-Level Security (RLS) and GUC context.

This module centralizes enforcement of the RLS & GUC contract:
- Every tenant-scoped query must run with `SET LOCAL app.jwt_tenant`,
  `app.user_id`, and `app.roles`.
- Provides utilities to apply and verify the context.
- Provides a safe way to derive `TenantContext` from ctxvars.

References:
- POLICIES.md → RLS & GUC CONTRACT (non-negotiable)
- Error handling: raise RlsNotSetError if GUCs not set/verified
"""
from __future__ import annotations

from typing import Dict, Optional
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from src.shared_.errors import RlsNotSetError
from src.shared_.utils.tenant_ctxvars import snapshot as ctx_snapshot
from src.shared_.database.types import TenantContext

logger = structlog.get_logger(__name__)


def tenant_context_from_ctxvars() -> Optional[TenantContext]:
    """
    Construct a TenantContext from ctxvars (if available).

    Returns:
        TenantContext if tenant_id is set, otherwise None.

    Typical Usage:
        - Called inside `session_from_ctxvars` helper.
        - Ensures request-scoped context is mapped into DB session.
    """    
    snap = ctx_snapshot()
    tid = snap.get("tenant_id")
    if not tid:
        return None
    roles = snap.get("roles")
    # Safely handle roles to ensure it's a list[str]
    raw_roles = snap.get("roles") or []
    if isinstance(raw_roles, str):
        roles = [r for r in raw_roles.split(",") if r]
    elif isinstance(raw_roles, (list, tuple)):
        roles = [str(r) for r in raw_roles if isinstance(r, str)]
    else:
        roles = []
        
    return TenantContext.from_maybe(
        tenant_id=str(tid),
        user_id=str(snap.get("user_id") or None),
        roles=roles if roles is not None else [],
    )

async def set_rls_gucs(
    session: AsyncSession, *, tenant_id: Optional[str], user_id: Optional[str], roles_csv: Optional[str]
) -> None:
    # GUCs must be set per-transaction (SET LOCAL) — RLS contract
    if tenant_id:
        await session.execute(text("SELECT set_config('app.jwt_tenant', :v, true)"), {"v": tenant_id})
    if user_id:
        await session.execute(text("SELECT set_config('app.user_id', :v, true)"), {"v": user_id})
    if roles_csv:
        await session.execute(text("SELECT set_config('app.roles', :v, true)"), {"v": roles_csv})

async def apply_rls_locals(session: AsyncSession, ctx: TenantContext) -> None:
    """
    Apply tenant/user/roles into Postgres session as LOCAL GUCs.

    Args:
        session: Async SQLAlchemy session.
        ctx: TenantContext containing tenant_id, user_id, and roles.

    Effect:
        Executes SET LOCAL commands inside current transaction scope:
            SET LOCAL app.jwt_tenant = '<tenant-uuid>';
            SET LOCAL app.user_id = '<user-uuid>';
            SET LOCAL app.roles = 'ROLE1,ROLE2,...';

    Notes:
        - GUCs are scoped to the transaction (`SET LOCAL`).
        - RLS policies (`enable_tenant_rls`) depend on these values.
    """
    try:
        if ctx.tenant_id:
            await session.execute(
                sa.text("SELECT set_config('app.jwt_tenant', :tenant_id, true)"),
                {"tenant_id": ctx.tenant_id},
            )
        if ctx.user_id:
            await session.execute(
                sa.text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": ctx.user_id},
            )
        if ctx.roles:
            roles_csv = ",".join(ctx.roles)
            await session.execute(
                sa.text("SELECT set_config('app.roles', :roles, true)"),
                {"roles": roles_csv},
            )
        logger.debug("RLS context applied", tenant_id=ctx.tenant_id, user_id=ctx.user_id, roles=ctx.roles)
    except Exception as e:
        logger.error("Failed to set tenant context", exc_info=True)
        raise RlsNotSetError(f"Failed to set RLS context: {e}") from e

async def verify_rls_context(session: AsyncSession) -> Dict[str, Optional[str]]:
    """
    Verify that tenant_id GUC is properly set in the current session.

    Args:
        session: Async SQLAlchemy session.

    Raises:
        RlsNotSetError: If `app.jwt_tenant` is NULL/empty.

    Why:
        - Prevents queries from running without tenant isolation.
        - Enforces POLICIES.md "RLS & GUC contract".
    """
    try:
        res = await session.execute(
            text(
                """
                SELECT
                    current_setting('app.jwt_tenant', true) AS tenant_id,
                    current_setting('app.user_id',   true) AS user_id,
                    current_setting('app.roles',     true) AS roles
                """
            )
        )
        row = res.fetchone()
        if not row or not row.tenant_id:
            raise RlsNotSetError("Tenant ID not set in RLS context")
        return {"tenant_id": row.tenant_id, "user_id": row.user_id, "roles": row.roles}
    except Exception as e:
        logger.error("Failed to verify RLS context", error=str(e))
        raise RlsNotSetError(f"RLS context verification failed: {e}") from e
