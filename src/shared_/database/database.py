# src/shared/database.py
"""
database.py — Async SQLAlchemy engine & session factory (tenant-agnostic)

This module owns:
  - Creating & caching the global AsyncEngine
  - Exposing an async session context manager (`get_async_session`)
  - Safe engine disposal for shutdown hooks and tests
  - Minimal, *tenant-agnostic* connection/session settings

Important:
  - Do NOT set tenant GUCs (RLS) here. RLS is applied in rls.py / sessions.py.
  - Keep this layer infra-only (no domain/app logic).

References:
  - POLICIES.md → Coding Standards, RLS & GUC Contract
  - SQLAlchemy 2.x async engine/session patterns
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Optional  # <-- ensure these
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
import structlog
from src.config import get_settings

logger = structlog.get_logger(__name__)

# ---- Globals ---------------------------------------------------------------

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None

settings = get_settings()

# ---- Engine lifecycle ------------------------------------------------------

async def create_database_engine(database_url: str) -> AsyncEngine:
    """
    Create and configure async database engine with safe pooling and connection args.
    """
    global _engine, _session_factory
    settings = get_settings()

    # Choose pool strategy
    if settings.IS_TESTING:
        poolclass = NullPool
        pool_size = 0
        max_overflow = 0
    else:
        pool_size = settings.database_pool_size
        max_overflow = settings.database_max_overflow

    _engine = create_async_engine(
        database_url,
        echo=settings.debug and not settings.is_production,
        # echo_pool removed (best controlled via logging config)
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "application_name": f"wcp-api-{settings.ENVIRONMENT}",
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
    """
    Return initialized session factory or lazily initialize it.

    Returns:
        async_sessionmaker[AsyncSession]: Configured session factory for async sessions.

    Raises:
        RuntimeError: If engine is not initialized and cannot be created.
    """
    global _session_factory
    if _session_factory is None:
        # Lazy initialization for compatibility with provided get_session()
        try:
            _session_factory = async_sessionmaker(
                bind=get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,  # Explicit flush control for performance
            )
            logger.debug("Session factory lazily initialized")
        except RuntimeError as e:
            logger.error("Failed to initialize session factory: engine not ready", error=str(e))
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
