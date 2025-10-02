"""
Context Dependencies
Provides UoW, services, etc.
"""
from __future__ import annotations


from shared.infrastructure.database.session import 
from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)
from src.identity.infrastructure.adapters.jwt_service import JWTService


def get_uow() -> IdentityUnitOfWork:
    """
    Get Identity Unit of Work instance.
    
    Returns:
        IdentityUnitOfWork configured with session factory
    """
    session_factory = get_session_factory()
    return IdentityUnitOfWork(session_factory)


def get_jwt_service() -> JWTService:
    """
    Get JWT service instance.
    
    Returns:
        JWTService configured with secret key
    """
    # In production, get secret from environment/config
    import os
    secret_key = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    return JWTService(secret_key=secret_key)