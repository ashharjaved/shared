"""
Identity API Routes
"""
from fastapi import APIRouter

from src.identity.api.routes import auth, users_route, organizations, roles

# Create main identity router
identity_router = APIRouter(prefix="/api/v1/identity", tags=["identity"])

# Include sub-routers
identity_router.include_router(auth.router, prefix="/auth", tags=["auth"])
identity_router.include_router(users_route.router, prefix="/users", tags=["users"])
identity_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
identity_router.include_router(roles.router, prefix="/roles", tags=["roles"])

__all__ = ["identity_router"]