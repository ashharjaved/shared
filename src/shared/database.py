from __future__ import annotations

from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional, Union
from uuid import UUID
from src.config import Settings
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Base(DeclarativeBase):
    """Declarative base for ORM models."""
    pass


# -------------------------------
# Sync engine / sessions
# -------------------------------
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine(db_url: str, echo: bool = False, pool_size: int = 5) -> Engine:
    """
    Create (once) and return a sync SQLAlchemy Engine with pooling and sane defaults.
    Also sets a default tenant GUC on connect to keep RLS safe by default.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            db_url,
            echo=echo,
            pool_size=pool_size,
            pool_pre_ping=True,
            pool_recycle=3600,
            isolation_level="READ COMMITTED",
        )

        @event.listens_for(_engine, "connect")
        def _set_default_tenant(dbapi_connection, connection_record):
            cur = dbapi_connection.cursor()
            cur.execute("SET app.jwt_tenant = '00000000-0000-0000-0000-000000000000'")
            cur.close()

    return _engine

engine = create_async_engine(Settings.DATABASE_URL, echo=Settings.DB_ECHO, pool_pre_ping=True, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
     async with AsyncSessionLocal() as session:
         yield session

def get_session_factory(engine: Engine) -> sessionmaker:
    """Create (once) and return a sync sessionmaker bound to the given engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
        )
    return _session_factory


@contextmanager
def session_scope(tenant_id: Union[UUID, str]) -> Generator[Session, None, None]:
    """
    Transactional scope with tenant GUC set for the entire block (sync).
    You must initialize via get_session_factory() before calling this.
    """
    if _session_factory is None:
        raise RuntimeError("Call get_session_factory(engine) before using session_scope().")
    session = _session_factory()
    try:
        set_tenant(session, tenant_id)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def set_tenant(session: Session, tenant_id: Union[UUID, str]) -> None:
    """Set tenant GUC on the current (sync) session safely."""
    session.execute(text("SET app.jwt_tenant = :tenant"), {"tenant": str(tenant_id)})


@contextmanager
def tenant_scope(session: Session, tenant_id: Union[UUID, str]) -> Generator[None, None, None]:
    """
    Temporarily override the tenant GUC for a block of work (sync).
    Restores the previous value afterwards.
    """
    prev_val: Optional[str] = session.execute(
        text("SELECT current_setting('app.jwt_tenant', true)")
    ).scalar_one_or_none()

    set_tenant(session, tenant_id)
    try:
        yield
    finally:
        session.execute(
            text("SELECT set_config('app.jwt_tenant', :val, true)"),
            {"val": prev_val or ""},
        )


# -------------------------------
# Async engine / sessions
# -------------------------------
_async_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_async_engine() -> AsyncEngine:
    """
    Create (once) and return the async SQLAlchemy engine from settings.DATABASE_URL.
    Also installs a connect hook (on the underlying sync engine) to set default tenant GUC.
    """
    from src.config import settings  # local import to avoid config import cycles
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(settings.DATABASE_URL, echo=settings.DB_ECHO, pool_pre_ping=True, future=True)


        @event.listens_for(_async_engine, "connect")
        def _set_default_tenant_async(dbapi_connection, connection_record):
            cur = dbapi_connection.cursor()
            cur.execute("SET app.jwt_tenant = '00000000-0000-0000-0000-000000000000'")
            cur.close()

    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create (once) and return an async sessionmaker bound to the async engine."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _async_session_factory


async def async_set_tenant(session: AsyncSession, tenant_id: Union[UUID, str]) -> None:
    """Set tenant GUC on the current (async) session safely."""
    await session.execute(text("SET app.jwt_tenant = :tenant"), {"tenant": str(tenant_id)})


@asynccontextmanager
async def async_session_scope(tenant_id: Union[UUID, str]) -> AsyncGenerator[AsyncSession, None]:
    """
    Transactional scope with tenant GUC set for the entire block (async).
    """
    factory = get_async_session_factory()
    async with factory() as session:
        await async_set_tenant(session, tenant_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def async_session_factory() -> AsyncSession:
    """
    Compatibility helper for FastAPI deps that do:
        async with async_session_factory() as session:
            ...
    Returns a *session instance* (context manager), not the factory.
    """
    factory = get_async_session_factory()
    return factory()

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency:
        async def endpoint(session: AsyncSession = Depends(get_session)): ...
    """
    async with async_session_factory() as session:
        yield session

__all__ = [
    "Base",
    "get_engine",
    "get_session_factory",
    "session_scope",
    "set_tenant",
    "tenant_scope",
    "get_async_engine",
    "get_async_session_factory",
    "async_session_factory",
    "async_session_scope",
    "async_set_tenant",
    "get_session",
]
