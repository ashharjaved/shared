"""
Context Dependencies
Provides UoW, services, etc.
"""
from __future__ import annotations

import os
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database import DatabaseSessionFactory
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.adapters.jwt_service import JWTService
from src.config import get_settings

# Get settings
settings = get_settings()

# Global singleton factory instance
_session_factory: DatabaseSessionFactory | None = None


def get_session_factory() -> DatabaseSessionFactory:
    """
    Get or create the global DatabaseSessionFactory singleton.
    
    Returns:
        DatabaseSessionFactory instance
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = DatabaseSessionFactory(
            database_url=settings.DATABASE_URL,
            echo=settings.debug,
            pool_size=20,
            max_overflow=10
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session with proper lifecycle management.
    
    Yields:
        AsyncSession instance
    """
    factory = get_session_factory()
    async for session in factory.get_session():
        yield session


def get_uow(
    session: AsyncSession = Depends(get_db_session),
) -> IdentityUnitOfWork:
    """
    Get Identity Unit of Work instance.
    
    Args:
        session: Database session from dependency injection
    
    Returns:
        IdentityUnitOfWork configured with the session
    """
    return IdentityUnitOfWork(session)


def get_jwt_service() -> JWTService:
    """
    Get JWT service instance.
    
    Returns:
        JWTService configured with secret key
    """
    secret_key = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    return JWTService(secret_key=secret_key)