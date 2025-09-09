# src/shared/database.py
"""
Async database configuration, session management, and per-request RLS context.
Merges engine lifecycle + helpers with verified RLS handling.
"""

from __future__ import annotations

import time
import inspect  # <-- add
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Union, Callable, Awaitable  # <-- ensure these
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool
import structlog  # type: ignore[import-not-found]
logger = structlog.get_logger(__name__)

from src.shared.config import get_settings
from src.shared.errors import RlsNotSetError
from src.shared.utils.tenant_ctxvars import snapshot as ctx_snapshot  # <-- use your helper

# ---- Globals ---------------------------------------------------------------

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


# ---- Engine lifecycle ------------------------------------------------------

async def create_database_engine(database_url: str) -> AsyncEngine:
    """
    Create and configure async database engine with safe pooling and connection args.
    """
    global _engine, _session_factory
    settings = get_settings()

    # Choose pool strategy
    if settings.is_testing:
        poolclass = NullPool
        pool_size = 0
        max_overflow = 0
    else:
        poolclass = QueuePool
        pool_size = settings.database_pool_size
        max_overflow = settings.database_max_overflow

    _engine = create_async_engine(
        database_url,
        echo=settings.debug and not settings.is_production,
        # echo_pool removed (best controlled via logging config)
        poolclass=poolclass,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "application_name": f"wcp-api-{settings.environment}",
                "statement_timeout": "30000",  # 30s
            }
        },
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        # autocommit removed for SQLAlchemy 2.x
    )

    # Smoke test
    try:
        async with _engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established")
    except Exception as e:
        logger.error("Failed to connect to database", error=str(e))
        raise

    return _engine


async def close_database_engine() -> None:
    """Dispose engine and reset factories."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        logger.info("Database engine disposed")
    _engine = None
    _session_factory = None


def get_engine() -> AsyncEngine:
    """Return initialized engine or raise."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call create_database_engine first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return initialized session factory or raise."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call create_database_engine first.")
    return _session_factory


# ---- Sessions --------------------------------------------------------------

@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession with automatic rollback on error and proper close.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---- RLS / Tenant Context --------------------------------------------------

class TenantContext:
    """
    Lightweight tenant context to be applied via SET LOCAL for the current txn.
    """
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        roles: Union[str, list[str], None] = None,
    ):
        self.tenant_id: Optional[str] = tenant_id
        self.user_id: Optional[str] = user_id
        # normalize to list[str]
        if roles is None:
            self.roles: list[str] = []
        elif isinstance(roles, str):
            self.roles = [r for r in roles.split(",") if r]
        else:
            self.roles = list(roles)

    def __repr__(self) -> str:
        return f"TenantContext(tenant_id={self.tenant_id}, user_id={self.user_id}, roles={self.roles})"
    
def tenant_context_from_ctxvars() -> Optional[TenantContext]:
    """
    Read ctxvars (set by HTTP middleware) and build a TenantContext.
    Returns None if no tenant_id is present.
    """
    snap = ctx_snapshot()
    tid = snap.get("tenant_id")
    if not tid:
        return None
    return TenantContext(
        tenant_id=str(tid),
        user_id=str(snap.get("user_id") or None),
        roles=list(snap.get("roles") or []),
    )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    snap = ctx_snapshot()
    # Fail fast if tenant missing (403 handler should convert)
    if not snap.get("tenant_id"):
        raise RuntimeError("Tenant context not set")  # your exception type here

    ctx = TenantContext(
        tenant_id=str(snap["tenant_id"]),
        user_id=str(snap.get("user_id")),
        roles=",".join(snap.get("roles", [])),
    )

    async with get_session_with_rls(ctx) as session:
        # Optional one-time guard per request (cheap)
        if getattr(settings, "DEBUG_VERIFY_RLS", False):
            await _verify_rls_context(session)
        yield session


async def _apply_rls_locals(session: AsyncSession, ctx: TenantContext) -> None:
    """
    Apply RLS via set_config(..., true) so values are local to the current txn.
    """
    try:
        if ctx.tenant_id:
            await session.execute(
                sa.text("SELECT set_config('app.jwt_tenant', :tenant_id, true)"),
                {"tenant_id": str(ctx.tenant_id)},
            )
        if ctx.user_id:
            await session.execute(
                sa.text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": str(ctx.user_id)},
            )
        if ctx.roles:
            roles_csv = ",".join(ctx.roles) if isinstance(ctx.roles, (list, tuple)) else str(ctx.roles)
            await session.execute(
                sa.text("SELECT set_config('app.roles', :roles, true)"),
                {"roles": roles_csv},
            )
        logger.debug("RLS context applied", tenant_id=ctx.tenant_id, user_id=ctx.user_id, roles=ctx.roles)
    except Exception as e:
        logger.error("Failed to set tenant context", exc_info=str(e))
        raise RlsNotSetError(f"Failed to set RLS context: {str(e)}")


async def _verify_rls_context(session: AsyncSession) -> Dict[str, Optional[str]]:
    """
    Read back current GUCs to ensure RLS context is present (best-effort).
    """
    try:
        result = await session.execute(
            text("""
                SELECT
                    current_setting('app.jwt_tenant', true)  AS tenant_id,
                    current_setting('app.user_id', true)      AS user_id,
                    current_setting('app.roles', true)        AS roles
            """)
        )
        row = result.fetchone()
        if not row:
            raise RlsNotSetError("Unable to retrieve RLS context")

        ctx = {"tenant_id": row.tenant_id, "user_id": row.user_id, "roles": row.roles}
        if not ctx["tenant_id"]:
            raise RlsNotSetError("Tenant ID not set in RLS context")
        return ctx  # tenant may be required; user/roles optional depending on endpoint
    except Exception as e:
        logger.error("Failed to verify RLS context", error=str(e))
        raise RlsNotSetError(f"RLS context verification failed: {str(e)}")


@asynccontextmanager
async def get_session_with_rls(
    tenant_id: str,
    user_id: Optional[str] = None,
    roles: Optional[list[str]] = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Session context manager that applies and verifies RLS GUCs for the request.
    """
    async with get_async_session() as session:
        ctx = TenantContext(tenant_id=tenant_id, user_id=user_id, roles=roles or [])
        # begin a tx scope so SET LOCAL persists for the work you do inside
        async with session.begin():
            await _apply_rls_locals(session, ctx)
            await _verify_rls_context(session)
            yield session  # keep using this txn or create subtransactions as needed

@asynccontextmanager
async def with_rls(
    session: AsyncSession,
    *,
    tenant_id: str,
    user_id: Optional[str] = None,
    roles: Optional[list[str]] = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager to ensure all operations within are executed with tenant RLS.
    Usage:
        async with with_rls(session, tenant_id=tid, user_id=uid, roles=csv_roles):
            await session.execute(...)
    """
    # Use SAVEPOINT when nested within existing tx; otherwise rely on outer tx.
    # We assume caller manages the transaction boundary (no commits here).
    ctx = TenantContext(tenant_id=tenant_id, user_id=user_id, roles=roles or [])
    await _apply_rls_locals(session, ctx)
    try:
        yield session
    finally:
        # No-op: SET LOCAL lives until txn ends. We intentionally do not reset.
        pass

@asynccontextmanager
async def session(require_tenant: bool = True) -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as s:
        async with s.begin():
            ctx = TenantContext()  # populate from request contextvars
            await _apply_rls_locals(s, ctx)
            await _verify_rls_context(s) if require_tenant else None
        try:
            yield s
        except Exception:
            await s.rollback()
            raise
        finally:
            await s.close()

# ---- Helpers: transactions & queries --------------------------------------

async def run_in_transaction(
    operation: Callable[[AsyncSession, Any], Any] | Callable[[AsyncSession, Any], Awaitable[Any]],
    tenant_context: Optional[TenantContext] = None,
    *args,
    **kwargs,
) -> Any:
    """
    Execute a callable/coroutine in a transaction, optionally with RLS context.
    """
    start = time.time()
    try:
        _ctx = tenant_context or tenant_context_from_ctxvars()
        async with get_async_session() as session:
            async with session.begin():
                if _ctx and _ctx.tenant_id:
                    await _apply_rls_locals(session, _ctx)

                # Support both async and sync callables
                if inspect.iscoroutinefunction(operation):
                    result = await operation(session, *args, **kwargs)
                else:
                    result = operation(session, *args, **kwargs)

        logger.debug("Transaction completed", extra={"duration_ms": int((time.time() - start) * 1000)})
        return result
    except Exception as e:
        logger.error("Transaction failed", extra={"error": str(e), "duration_ms": int((time.time() - start) * 1000)})
        raise

async def execute_query(
    query: Union[str, sa.sql.Executable],
    params: Optional[Dict[str, Any]] = None,
    tenant_context: Optional[TenantContext] = None,
):
    """
    Execute a raw or SQLAlchemy query with optional RLS tenant context.
    """
    async def _op(session: AsyncSession):
        if isinstance(query, str):
            return await session.execute(sa.text(query), params or {})
        return await session.execute(query, params or {})

    return await run_in_transaction(_op, tenant_context)


async def get_tenant_from_jwt_context() -> Optional[str]:
    """
    Convenience helper to read jwt_tenant() if your DB exposes that helper.
    """
    try:
        async with get_async_session() as session:
            result = await session.execute(sa.text("SELECT jwt_tenant()"))
            return str(result.scalar_one_or_none() or "")
    except Exception as e:
        logger.warning("Could not retrieve tenant from context", exc_info=str(e))
        return None


# ---- Health checks ---------------------------------------------------------

class DatabaseHealthCheck:
    """Database health inspection utilities."""

    @staticmethod
    async def check_connection() -> Dict[str, Any]:
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                res = await conn.execute(text("SELECT 1 AS health_check"))
                row = res.fetchone()
                if not row or row.health_check != 1:
                    return {"healthy": False, "error": "health check failed"}

            # pool metrics (where available)
            payload: Dict[str, Any] = {"healthy": True}
            pool = engine.pool
            if hasattr(pool, "size"):
                payload["pool_size"] = pool.size()  # type: ignore[attr-defined]
            if hasattr(pool, "checkedin"):
                payload["checked_in"] = pool.checkedin()  # type: ignore[attr-defined]
            if hasattr(pool, "checkedout"):
                payload["checked_out"] = pool.checkedout()  # type: ignore[attr-defined]
            if hasattr(pool, "overflow"):
                payload["overflow"] = pool.overflow()  # type: ignore[attr-defined]
            return payload
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {"healthy": False, "error": str(e)}

    @staticmethod
    async def check_rls_functions() -> Dict[str, Any]:
        """Verify jwt_tenant() exists (optional)."""
        try:
            async with get_async_session() as session:
                res = await session.execute(
                    text("""SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'jwt_tenant') AS jwt_tenant_exists""")
                )
                row = res.fetchone()
                ok = (row.jwt_tenant_exists if row else False)
                return {"healthy": ok, "jwt_tenant_function": ok}
        except Exception as e:
            logger.error("RLS functions health check failed", error=str(e))
            return {"healthy": False, "error": str(e)}


# ---- FastAPI dependency & app hooks ---------------------------------------

async def get_db_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to inject a plain session (no RLS)."""
    async with get_async_session() as session:
        yield session


# Optional convenience aliases if your app expects these:
init_database = create_database_engine
close_database = close_database_engine