# src/dependencies.py
"""
FastAPI dependencies for DB access with strict RLS GUC setup.

Key contract:
- Before ANY tenant-scoped query, set:
    SET LOCAL app.jwt_tenant = <tenant_id>
    SET LOCAL app.user_id    = <user_id or NIL_UUID>
    SET LOCAL app.roles      = <role or ''>
- Open a transaction so SET LOCAL persists for the life of the request dependency.
"""

from __future__ import annotations

from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.database import SessionLocal, get_sessionmaker
from src.shared.security import decode_jwt

# Nil UUID constant to avoid NULL user_id in SQL when not available (defensive)
NIL_UUID = UUID("00000000-0000-0000-0000-000000000000")


def _extract_bearer_token_from_header(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")
    return authorization.split(" ", 1)[1].strip()


async def _apply_rls_gucs(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: Optional[UUID],
    role: Optional[str],
) -> None:
    # Exact names per RLS_GUC_CONTRACT.md
    await session.execute(text("SET LOCAL app.jwt_tenant = :tenant_id"), {"tenant_id": str(tenant_id)})
    await session.execute(text("SET LOCAL app.user_id = :user_id"), {"user_id": str(user_id or NIL_UUID)})
    await session.execute(text("SET LOCAL app.roles = :roles"), {"roles": str(role or "")})


async def assert_rls_set(session: AsyncSession) -> None:
    """
    Defensive guard to ensure RLS GUCs are present before queries.
    Hard-fails if app.jwt_tenant is missing/empty.
    """
    res = await session.execute(
        text(
            """
            SELECT
              NULLIF(current_setting('app.jwt_tenant', true), '') AS tenant_id,
              current_setting('app.user_id', true)                AS user_id,
              current_setting('app.roles', true)                  AS roles
            """
        )
    )
    tenant_id, _, _ = res.one()
    if tenant_id is None:
        raise RuntimeError("RLS GUC 'app.jwt_tenant' is not set in this transaction")


async def get_db_session(
    request: Request,
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an AsyncSession with RLS GUCs set (transaction scoped).

    Flow:
      1) Extract & decode Bearer JWT (expects claims: sub, tenant_id, role).
      2) Begin a transaction and SET LOCAL app.jwt_tenant, app.user_id, app.roles.
      3) Assert RLS context present (defensive).
      4) Attach context to request.state for logging/audit; yield session.

    Notes:
      - This dependency is the canonical way to access tenant-scoped tables.
      - Bootstrap and background jobs may use `tenant_override` or custom helpers.
    """
    token = _extract_bearer_token_from_header(authorization)
    try:
        claims = decode_jwt(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    try:
        tenant_id = UUID(str(claims["tenant_id"]))
        user_id = UUID(str(claims["sub"]))
        role = str(claims.get("role") or "")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_claims")

    async with sessionmaker() as session:
        # Transaction scope ensures SET LOCAL persists across all ops in this request
        async with session.begin():
            await _apply_rls_gucs(session, tenant_id=tenant_id, user_id=user_id, role=role)
            await assert_rls_set(session)

            # Expose to middleware/handlers for structured logging
            if hasattr(request, "state"):
                request.state.tenant_id = tenant_id
                request.state.user_id = user_id
                request.state.role = role

            yield session
        # Commit/rollback handled by `session.begin()`


class tenant_override:
    """
    Async context manager to override tenant GUC during bootstrap/system flows.

    Usage:
        async with session.begin():
            async with tenant_override(session, tenant_id):
                ... do inserts/updates bound to that tenant ...
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def __aenter__(self):
        await self.session.execute(text("SET LOCAL app.jwt_tenant = :tenant_id"), {"tenant_id": str(self.tenant_id)})

    async def __aexit__(self, exc_type, exc, tb):
        # SET LOCAL reverts automatically at transaction end
        return False
