"""
Database Session Factory
Creates async SQLAlchemy sessions with proper configuration
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class DatabaseSessionFactory:
    """
    Factory for creating async database sessions.
    
    Manages the async engine and session maker.
    Supports connection pooling and proper lifecycle management.
    """
    
    def __init__(self, database_url: str, echo: bool = False, pool_size: int = 20, max_overflow: int = 10) -> None:
        """
        Initialize session factory with database connection.
        
        Args:
            database_url: PostgreSQL connection string (asyncpg)
            echo: Whether to log SQL statements (debug mode)
            pool_size: Connection pool size
            max_overflow: Max overflow connections beyond pool_size
        """
        self.database_url = database_url
        self.echo = echo
        
        # Create async engine
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
        
        # Create session factory
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
            autoflush=False,  # Manual flushing for better control
            autocommit=False,  # Explicit transaction management
        )
        
        logger.info(
            "Database session factory initialized",
            extra={"pool_size": pool_size, "max_overflow": max_overflow},
        )
    
    async def create_session(self) -> AsyncSession:
        """
        Create a new async session.
        
        Returns:
            New AsyncSession instance
        """
        return self.session_factory()
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager for sessions (for dependency injection).
        
        Yields:
            AsyncSession instance
            
        Usage:
            async with factory.get_session() as session:
                # Use session
        """
        async with self.session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Session error, rolled back: {e}")
                raise
            finally:
                await session.close()
    
    async def dispose(self) -> None:
        """Close all connections and dispose of the engine."""
        await self.engine.dispose()
        logger.info("Database engine disposed")