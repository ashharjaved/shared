# src/shared/database.py
"""
Database engine and session management with tenant context support.
Key responsibilities:
- Creates SQLAlchemy engine with connection pooling
- Provides session factory with tenant context management
- Enforces RLS via app.jwt_tenant GUC
- Configures transaction isolation level (READ COMMITTED)
Important:
- NEVER bypass tenant context - all queries must be tenant-scoped
- Use session.get_tenant()/set_tenant() to manage context
"""
from typing import Optional, Generator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.engine import Engine
class Base(DeclarativeBase):
    pass

_engine: Optional[Engine] = None
_session_factory = None
_async_session_factory = None


def get_engine(db_url: str, echo: bool = False, pool_size: int = 5) -> Engine:
    """Create and configure SQLAlchemy engine with connection pooling."""
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
        def set_tenant_guard(dbapi_connection, connection_record):
            """Ensure tenant context is set on new connections."""
            cursor = dbapi_connection.cursor()
            cursor.execute("SET app.jwt_tenant = '00000000-0000-0000-0000-000000000000'")
            cursor.close()
            
    return _engine

def get_session_factory(engine: Engine):
    """Create session factory with tenant context management."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory

# def get_async_session_factory(async_engine):
    # """Create async session factory with tenant context management."""
    # global _async_session_factory
    # if _async_session_factory is None:
    #     _async_session_factory = async_sessionmaker(
    #         bind=async_engine,
    #         expire_on_commit=False,
    #         class_=AsyncSession,
    #     )
    # return _async_session_factory

@contextmanager
def session_scope(tenant_id: UUID):
    """Provide a transactional scope around a series of operations with tenant context."""
    session = _session_factory()
    try:
        session.execute(f"SET app.jwt_tenant = '{tenant_id}'")
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def set_tenant(session: Session, tenant_id: UUID) -> None:
    """Set tenant context for the current session."""
    session.execute(f"SET app.jwt_tenant = '{tenant_id}'")

@contextmanager
def tenant_scope(session: Session, tenant_id: UUID | str) -> Generator[None, None, None]:
    """
    Context manager to temporarily set the tenant GUC for a block of work.

    Example:
        with tenant_scope(session, tenant_id):
            session.query(Message).count()
    """
    # Read previous value (if any)
    prev_val: Optional[str] = session.execute(
        text("SELECT current_setting('app.jwt_tenant', true)")
    ).scalar_one_or_none()

    # Set new tenant id
    set_tenant(session, tenant_id)
    try:
        yield
    finally:
        # Restore previous value (transaction-scoped)
        session.execute(
            text("SELECT set_config('app.jwt_tenant', :val, true)"),
            {"val": prev_val if prev_val is not None else ""},
        )

_async_engine = None
_async_session_factory = None

def _get_async_engine():
    """
    Lazy init async engine from settings.DATABASE_URL
    """
    from src.config import settings
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return _async_engine

def async_session_factory():
    """
    Return an async session factory, compatible with src.dependencies.get_session().
    Usage:
        async with async_session_factory() as session: ...
    """
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(bind=_get_async_engine(), expire_on_commit=False, class_=AsyncSession)
    return _async_session_factory()

__all__ = [
    'Base',
    'get_engine',
    'get_session_factory',
    'session_scope',
    'set_tenant',
    'tenant_scope',
]
