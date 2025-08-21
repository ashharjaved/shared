from __future__ import annotations

from contextlib import contextmanager
from typing import AsyncGenerator, Generator

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.config import settings
from src.shared.security import get_principal
    

class Base(DeclarativeBase):
    """Declarative base for ORM models."""
    pass
# ---------------------------------------------------------------------
# Single sources of truth (created once, reused)
# ---------------------------------------------------------------------
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_session_factory: sessionmaker[Session] | None = None


# ---------------------------------------------------------------------
# Async engine + session factory (for FastAPI routes/services)
# ---------------------------------------------------------------------


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create (once) and return the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _async_session_factory

# Legacy alias (some modules may call this name)
def async_session_factory() -> async_sessionmaker[AsyncSession]:
    return get_async_session_factory()


async def get_session(principal=Depends(get_principal)) -> AsyncGenerator[AsyncSession, None]:
    async_session_factory_instance = async_session_factory()
    async with async_session_factory_instance() as session:
        # Set per-request tenant for RLS
        tid = getattr(principal, "tenant_id", None) if principal else None
        if tid:
            from sqlalchemy import text
            #await session.execute(text("SET LOCAL app.jwt_tenant = :tid"), {"tid": str(tid)})
            await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": str(tid)},)
            result = await session.execute(text("SHOW app.jwt_tenant"))
            tenant_id = result.scalar_one_or_none()
            print("Current tenant in DB session:", tenant_id)

        yield session


# ---------------------------------------------------------------------
# Sync engine + session factory (for scripts, migrations, admin tasks)
# ---------------------------------------------------------------------
def get_sync_engine() -> Engine:
    """
    Expose a synchronous Engine. We return the underlying sync_engine of the
    AsyncEngine so the DSN stays centralized.
    If later you want a separate sync DSN/driver, add DATABASE_URL_SYNC and
    create a dedicated sync engine here.
    """
    return get_async_engine().sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    """Create (once) and return the sync session factory."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=get_sync_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _sync_session_factory


@contextmanager
def get_db_sync() -> Generator[Session, None, None]:
    """
    Usage (scripts/admin):
        from sqlalchemy import text
        from src.shared.database import get_db_sync

        with get_db_sync() as db:
            db.execute(text("SELECT 1"))
            db.commit()
    """
    sfactory = get_sync_session_factory()
    with sfactory() as session:
        yield session

def get_async_engine() -> AsyncEngine:
    """Create (once) and return the async SQLAlchemy engine with connect hooks."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=getattr(settings, "DB_ECHO", False),
            pool_pre_ping=True,
        )

        # Attach connect hook to enforce statement_timeout
        def _on_connect(dbapi_connection, connection_record):
            timeout = getattr(settings, "DB_STATEMENT_TIMEOUT_MS", None)
            if timeout:
                with dbapi_connection.cursor() as cur:
                    cur.execute(f"SET statement_timeout = {int(timeout)}")

        event.listen(_async_engine.sync_engine, "connect", _on_connect)

    return _async_engine


# --- keep all your existing code above unchanged ---

__all__ = [
    # async
    "get_async_engine",
    "get_async_session_factory",
    "async_session_factory",
    "get_session",
    # sync
    "get_sync_engine",
    "get_sync_session_factory",
    "get_db_sync",
    # orm base
    "Base",
]
