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
    # await session.execute(text("SET LOCAL app.jwt_tenant = :tenant_id"), {"tenant_id": str(tenant_id)})
    # await session.execute(text("SET LOCAL app.user_id = :user_id"), {"user_id": str(user_id or NIL_UUID)})
    # await session.execute(text("SET LOCAL app.roles = :roles"), {"roles": str(role or "")})
    await session.execute(text("SELECT set_config('app.jwt_tenant', :v, true)"), {"v": str(tenant_id)})
    await session.execute(text("SELECT set_config('app.user_id', :v, true)"), {"v": str(user_id or NIL_UUID)})
    await session.execute(text("SELECT set_config('app.roles', :v, true)"), {"v": str(role or "")})


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
        #await self.session.execute(text("SET LOCAL app.jwt_tenant = :tenant_id"), {"tenant_id": str(self.tenant_id)})
        await self.session.execute(
            text("SELECT set_config('app.jwt_tenant', :v, true)"),
            {"v": str(self.tenant_id)},
        )

    async def __aexit__(self, exc_type, exc, tb):
        # SET LOCAL reverts automatically at transaction end
        return False


# -----------------------------------------------------------------------------
# Raw DB dependency (no RLS)
#
# Some flows such as initial bootstrap and login occur before a JWT is available.
# Those flows still need a database session but cannot satisfy the strict JWT
# requirements enforced by `get_db_session`. This helper yields an AsyncSession
# without attempting to extract or decode an Authorization header or set any
# tenant-specific RLS context. Callers are responsible for setting RLS GUCs via
# `set_rls_gucs` before issuing tenant-scoped queries.
#
# Example usage::
#
#     async def login(..., db: AsyncSession = Depends(get_db)):
#         tenant = await tenants.get_by_name(name)
#         async with db.begin():
#             await set_rls_gucs(db, tenant_id=str(tenant.id), user_id=None, roles=None)
#             ...

async def get_db(
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        async with session.begin():
            yield session

# ============================
# Stage-2: Core Platform DI
# ============================
from typing import Callable, Awaitable
from uuid import UUID
from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.cache import get_redis
from src.shared.database import async_session_factory
from src.config import get_settings
from src.shared.security import decode_jwt  # assuming Stage-1 provides this

from src.platform.infrastructure.cache import ConfigCache
from src.platform.infrastructure.Repositories import config_repository
from src.platform.domain.services import ConfigurationService


# --- Common DI already present in Stage-1; re-export safe wrappers if needed ---


settings = get_settings()

def get_current_tenant(request: Request) -> UUID:
    """
    Resolve tenant_id from request context.
    Expected: Stage-1 auth middleware sets request.state.tenant_id (from JWT).
    """
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        # fallback to Authorization header if middleware not yet added here
        authz = request.headers.get("Authorization", "")
        if authz.lower().startswith("bearer "):
            token = authz.split(" ", 1)[1].strip()
            try:
                payload = decode_jwt(token)
                tid = UUID(payload.get("tenant_id"))
                request.state.tenant_id = tid
            except Exception:
                pass
    if tid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing tenant context"},
        )
    return tid


# --- ConfigurationService DI ---

async def provide_configuration_service(
    redis = Depends(get_redis),
    settings = Depends(get_settings),
) -> ConfigurationService:
    cache = ConfigCache(redis_client=redis, ttl_seconds=settings.CONFIG_CACHE_TTL)
    repo = config_repository.ConfigRepository()
    return ConfigurationService(repo=repo, cache=cache)


# --- Rate Limiter (per-tenant, per-endpoint; sliding window via ZSET) ---

def rate_limit_dependency(endpoint_key: str) -> Callable[..., Awaitable[None]]:
    """
    Usage: Depends(rate_limit_dependency("GET:/platform/config"))
    Sliding window using Redis ZSET with timestamps (ms).
    Key: "ratelimit:{tenant_id}:{endpoint_key}"
    """
    async def _dep(
        request: Request,
        tenant_id: UUID = Depends(get_current_tenant),
        redis = Depends(get_redis),
        settings = Depends(get_settings),
    ) -> None:
        import time
        now_ms = int(time.time() * 1000)
        window_ms = settings.RATE_LIMIT_WINDOW * 1000
        key = f"ratelimit:{tenant_id}:{endpoint_key}"

        # Remove entries outside the window
        await redis.zremrangebyscore(key, 0, now_ms - window_ms)
        # Add current hit
        await redis.zadd(key, {str(now_ms): now_ms})
        # Get count
        count = await redis.zcard(key)
        # Set TTL a bit beyond window
        await redis.pexpire(key, window_ms + 1000)

        if count > settings.RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "rate_limited", "message": "Rate limit exceeded", "details": {
                    "limit": settings.RATE_LIMIT_REQUESTS,
                    "window_seconds": settings.RATE_LIMIT_WINDOW,
                }},
            )
        return None

    return _dep