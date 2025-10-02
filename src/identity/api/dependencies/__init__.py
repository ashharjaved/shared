"""
Identity API Dependencies
FastAPI dependency injection for auth and context
"""
from src.identity.api.dependencies.auth import (
    get_current_user,
    get_current_active_user,
    require_roles,
    CurrentUser,
)
from src.identity.api.dependencies.context import (
    get_uow,
    get_jwt_service,
)

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_roles",
    "CurrentUser",
    "get_uow",
    "get_jwt_service",
]