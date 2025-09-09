from __future__ import annotations

from typing import Optional
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text
import structlog

from src.shared.config import get_settings

logger = structlog.get_logger(__name__)

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def create_database_engine(database_url: str) -> AsyncEngine:
    """
    Initialize the async engine & session factory with sane pooling defaults.
    """
    global _engine, _session_factory
    settings = get_settings()

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
    )

    # Smoke test
    async with _engine.begin() as conn:
        await conn.execute(sa.text("SELECT 1"))

    logger.info("Database connection established")
    return _engine


async def close_database_engine() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        logger.info("Database engine disposed")
    _engine = None
    _session_factory = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialized. Call create_database_engine first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call create_database_engine first.")
    return _session_factory