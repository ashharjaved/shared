from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text

# NOTE:
# - This module does not create engines; it expects an async_sessionmaker to be
#   set on `app.state.db_sessionmaker` at startup (see shared/database.py).
# - It enforces the RLS GUC contract on every DB transaction:
#     SET LOCAL app.jwt_tenant = <tenant_id>
#     SET LOCAL app.user_id    = <user_id>
#     SET LOCAL app.roles      = <role>
#   (see /docs: RLS_GUC_CONTRACT.md)
#
# - For bootstrap routes (no JWT yet), use `tenant_override()` to temporarily set
#   the GUC to the freshly-created tenant_id before inserting tenant‑scoped rows
#   like `users`. Example:
#       async with tenant_override(session, new_tenant_id):
#           await repo.create_owner_user(...)
#
# - We never bypass RLS.

# --------------------------------------------------------------------
# Structured logger
# --------------------------------------------------------------------
logger = logging.getLogger("app.dependencies")

# --------------------------------------------------------------------------- #
# Constants & simple helpers
# --------------------------------------------------------------------------- #

NIL_UUID = UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True)
class Principal:
    tenant_id: UUID
    user_id: Optional[UUID]
    role: Optional[str]


def _decode_bearer(token: str) -> dict:
    """
    Decodes a JWT *without* validating keys here; validation/expiration is
    expected to be handled in the auth layer. We keep this minimal to avoid
    tight coupling. If your project exposes a verified decode (e.g. in
    shared.security), import and use that instead.
    """
    try:
        # Lazy import to avoid hard dependency if your module name differs.
        from src.shared.security import decode_jwt  # type: ignore
    except Exception:
        # Best-effort, non-validating decode path (for local/dev only).
        # If this path is hit, auth layer should already have validated.
        import base64
        import json

        parts = token.split(".")
        if len(parts) != 3:
            return {}
        def _pad(b: str) -> str:
            return b + "=" * (-len(b) % 4)
        try:
            payload = json.loads(
                base64.urlsafe_b64decode(_pad(parts[1])).decode("utf-8")
            )
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    else:
        return decode_jwt(token) or {}


def _extract_principal_from_request(request: Request, authorization: Optional[str]) -> Principal:
    """
    Pulls tenant_id/user_id/role from (in order):
      1) request.state (middleware may have set these already)
      2) Bearer JWT claims (Authorization header)
      3) Fallback NIL tenant for unauthenticated/tenant-agnostic routes
    """
    # 1) Middleware-provided (preferred)
    st = getattr(request, "state", None)
    st_tenant: Optional[UUID] = getattr(st, "tenant_id", None)
    st_user: Optional[UUID] = getattr(st, "user_id", None)
    st_role: Optional[str] = getattr(st, "role", None)

    if st_tenant:
        return Principal(tenant_id=st_tenant, user_id=st_user, role=st_role)

    # 2) Authorization: Bearer <jwt>
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        claims = _decode_bearer(token)
        try:
            tenant_id = UUID(str(claims.get("tenant_id")))
        except Exception:
            tenant_id = NIL_UUID
        user_id = None
        if claims.get("sub"):
            try:
                user_id = UUID(str(claims["sub"]))
            except Exception:
                user_id = None
        # Single-role model per frozen SQL
        role = claims.get("role") or claims.get("roles") or None
        if isinstance(role, (list, tuple)):
            role = role[0] if role else None
        return Principal(tenant_id=tenant_id or NIL_UUID, user_id=user_id, role=role)

    # 3) Fallback (tenant-agnostic tables like `tenants` are not RLS'd)
    return Principal(tenant_id=NIL_UUID, user_id=None, role=None)


async def _apply_rls_gucs(session: AsyncSession, principal: Principal) -> None:
    """
    Executes the required SET LOCAL statements for the current transaction.
    Must be invoked *inside* an active transaction (session.begin()).
    """
    await session.execute(
        #text("SET LOCAL app.jwt_tenant = :tenant_id").bindparams(tenant_id=str(principal.tenant_id))
        text("SELECT set_config('app.jwt_tenant', :tenant_id, true)").bindparams(tenant_id=str(principal.tenant_id))
    )
    await session.execute(
        #text("SET LOCAL app.user_id = :user_id").bindparams(user_id=str(principal.user_id or NIL_UUID))
        text("SELECT set_config('app.jwt_user', :user_id, true)").bindparams(user_id=str(principal.user_id))
    )
    await session.execute(
        #text("SET LOCAL app.roles = :roles").bindparams(roles=str(principal.role or ""))
        text("SELECT set_config('app.jwt_role', :role, true)").bindparams(role=str(principal.role))
    )


# --------------------------------------------------------------------------- #
# Public dependencies
# --------------------------------------------------------------------------- #

async def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    sm = getattr(request.app.state, "db_sessionmaker", None)
    if sm is None:
        raise RuntimeError(
            "DB sessionmaker not configured on app.state.db_sessionmaker. "
            "Initialize it during startup (see shared/database.py)."
        )
    return sm


async def get_db_session(
    request: Request,
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an AsyncSession with RLS GUCs set *per transaction*.

    All repository calls during a request share this session/transaction
    and thus remain safely tenant-scoped.
    """
    principal = _extract_principal_from_request(request, authorization)

    async with sessionmaker() as session:
        # Open a transaction so SET LOCAL sticks for the life of the dependency.
        async with session.begin():
            await _apply_rls_gucs(session, principal)
            # Stash for logging/handlers
            if hasattr(request, "state"):
                request.state.tenant_id = principal.tenant_id
                request.state.user_id = principal.user_id
                request.state.role = principal.role
            yield session
        # No explicit commit here; handlers/services should manage writes.
        # The 'begin()' context guarantees rollback on exception.


# --------------------------------------------------------------------------- #
# Tenant override for bootstrap flows
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def tenant_override(session: AsyncSession, tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """
    Temporarily sets the tenant GUC within the *current transaction* to the
    provided tenant_id. Use this right after creating a new tenant (table
    `tenants` is platform-scoped, no RLS), when you immediately need to insert
    tenant-scoped rows (e.g., the first owner user) in the same request.

    Example:
        async with session.begin():
            # 1) create tenant (no RLS on `tenants`)
            new_tenant_id = await tenants_repo.create(...)

            # 2) ensure RLS matches the new tenant for subsequent inserts
            async with tenant_override(session, new_tenant_id):
                await users_repo.create_owner(...)

            # optional: other ops...

    IMPORTANT:
    - Works only inside an active transaction (caller uses session.begin()).
    - We deliberately do not try to "restore" the previous tenant GUC; SET LOCAL
      applies to the current transaction and will revert automatically once the
      transaction ends.
    """
    if not session.in_transaction():
        raise RuntimeError("tenant_override() requires an active transaction (session.begin()).")

    await session.execute(
        text("SET LOCAL app.jwt_tenant = :tenant_id").bindparams(tenant_id=str(tenant_id))
    )
    try:
        yield session
    finally:
        # No-op: SET LOCAL lifetime == current transaction.
        pass


# --------------------------------------------------------------------------- #
# Convenience accessor for handlers/services (optional)
# --------------------------------------------------------------------------- #

def require_tenant_id(request: Request) -> UUID:
    """
    Helper for routes that MUST have a tenant in context.
    Raises 401 if no tenant_id is present (e.g., missing/invalid JWT).
    """
    tid: Optional[UUID] = getattr(request.state, "tenant_id", None)
    if not tid or tid == NIL_UUID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Tenant context missing"},
        )
    return tid
