# src/shared/database.py
from __future__ import annotations
import os
from typing import Callable, Optional, TYPE_CHECKING
from uuid import UUID
from dotenv import load_dotenv

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from redis.asyncio import Redis

from sqlalchemy import Tuple, text


load_dotenv()

class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""
    pass

# NOTE: DB is the source of truth (see REDIS policy). Pool pre-ping enabled.
# Add URL validation
DATABASE_URL = os.getenv("DATABASE_URL") or ""

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _create_engine() -> AsyncEngine:
    """Create a single AsyncEngine for the app."""
    return create_async_engine(
        DATABASE_URL,
        echo=os.getenv("SQLALCHEMY_ECHO", "0") == "1",
        future=True,
        pool_pre_ping=True,
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    )


def get_engine() -> AsyncEngine:
    """Lazy singleton engine (prevents '_engine is unbound')."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session() -> async_sessionmaker[AsyncSession]:
    """Lazy singleton session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# (Optional) FastAPI dependency with tenant RLS context
async def db_session(tenant_id: str | None = None):
    Session = get_session()
    async with Session() as session:
        if tenant_id:
            # enforce RLS context for this session
            await session.execute(
                text("SELECT set_config('app.jwt_tenant', :tid, true)"),
                {"tid": tenant_id},
            )
        yield session

# --- Repo factories (lazy imports to avoid circulars) -------------------------

if TYPE_CHECKING:
    # Only for type checking; no runtime imports here
    from redis.asyncio import Redis
    from src.messaging.domain.types import GetChannelLimits
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

def make_channel_repo(
    *,
    tenant_id: Optional[UUID],
    encrypt: Callable[[str], str],
    decrypt: Callable[[str], str],
    session_factory: async_sessionmaker[AsyncSession],
):
    # If tenant_id is None (webhook path), you’ll set GUC per-query using resolved tenant when possible.
    # Otherwise, pass the tenant_id given by get_current_user().
    from src.messaging.infrastructure.repositories.channel_repository_impl import PostgresChannelRepository
    return PostgresChannelRepository(
        session_factory=session_factory,
        tenant_id=tenant_id or UUID(int=0),  # placeholder; your repo may accept Optional and handle per-call
        encrypt=encrypt,
        decrypt=decrypt,
    )

def make_message_repo(
    *,
    tenant_id: Optional[UUID],
    session_factory: async_sessionmaker[AsyncSession],
    redis: Optional[Redis],
    get_channel_limits: GetChannelLimits,
):
    from src.messaging.infrastructure.repositories.message_repository_impl import PostgresMessageRepository
    return PostgresMessageRepository(
        session_factory=session_factory,
        tenant_id=tenant_id or UUID(int=0),
        redis=redis,
        get_channel_limits=get_channel_limits,
    )
async def set_rls_guc(
    session: AsyncSession,
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    roles: str | None = None,
) -> None:
    """
    Conforms to RLS_GUC_CONTRACT.md:
      - app.jwt_tenant
      - app.user_id
      - app.roles
    """
    # Use a SAVEPOINT so we don't interfere with caller tx semantics
    async with session.begin_nested():
        if tenant_id is not None:
            await session.execute(text("SELECT set_config('app.jwt_tenant', :v, true)"), {"v": str(tenant_id)})
        if user_id is not None:
            await session.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})
        if roles is not None:
            await session.execute(text("SELECT set_config('app.roles', :r, true)"), {"r": str(roles)})
