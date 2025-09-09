from __future__ import annotations

from typing import Dict, Optional
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from src.shared.errors import RlsNotSetError
from src.shared.utils.tenant_ctxvars import snapshot as ctx_snapshot
from src.shared.database.types import TenantContext

logger = structlog.get_logger(__name__)


def tenant_context_from_ctxvars() -> Optional[TenantContext]:
    snap = ctx_snapshot()
    tid = snap.get("tenant_id")
    if not tid:
        return None
    roles = snap.get("roles")
    return TenantContext.from_maybe(
        tenant_id=str(tid),
        user_id=str(snap.get("user_id") or None),
        roles=roles if roles is not None else [],
    )


async def apply_rls_locals(session: AsyncSession, ctx: TenantContext) -> None:
    """
    Apply RLS via set_config(..., true) so values are local to the current txn.
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
    Best-effort check that GUCs are set (especially tenant).
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
