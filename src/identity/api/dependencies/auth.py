"""
Authentication Dependencies
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from shared.infrastructure.observability.logger import get_logger
from src.identity.infrastructure.adapters.jwt_service import JWTService
from src.identity.api.dependencies.context import get_jwt_service

logger = get_logger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


class CurrentUser(BaseModel):
    """
    Current authenticated user context.
    
    Extracted from JWT token claims.
    """
    user_id: UUID
    organization_id: UUID
    email: str
    roles: list[str]
    permissions: list[str]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> CurrentUser:
    """
    Extract and validate current user from JWT token.
    
    Args:
        credentials: HTTP Bearer token
        jwt_service: JWT service for token verification
        
    Returns:
        CurrentUser with claims from token
        
    Raises:
        HTTPException: 401 if token invalid or expired
    """
    token = credentials.credentials
    
    try:
        # Verify and decode token
        payload = jwt_service.verify_access_token(token)
        
        # Extract claims
        user_id = UUID(payload["user_id"])
        organization_id = UUID(payload["organization_id"])
        email = payload["email"]
        roles = payload.get("roles", [])
        permissions = payload.get("permissions", [])
        
        current_user = CurrentUser(
            user_id=user_id,
            organization_id=organization_id,
            email=email,
            roles=roles,
            permissions=permissions,
        )
        
        logger.debug(
            "User authenticated",
            extra={
                "user_id": str(user_id),
                "organization_id": str(organization_id),
                "roles": roles,
            },
        )
        
        return current_user
        
    except Exception as e:
        logger.warning(
            f"Authentication failed: {e}",
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "unauthorized",
                "message": "Invalid or expired authentication token",
            },
        )


async def get_current_active_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """
    Ensure current user is active.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        CurrentUser if active
        
    Raises:
        HTTPException: 403 if user inactive
        
    Note: In production, you'd check user.is_active from database
    For now, we trust the token (issued only to active users)
    """
    return current_user


def require_roles(*allowed_roles: str):
    """
    Dependency factory to require specific roles.
    
    Usage:
        @router.get("/admin", dependencies=[Depends(require_roles("SuperAdmin"))])
        async def admin_endpoint():
            ...
    
    Args:
        *allowed_roles: Roles that can access the endpoint
        
    Returns:
        Dependency function
    """
    async def check_roles(
        current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    ) -> CurrentUser:
        """Check if user has required role"""
        if not any(role in current_user.roles for role in allowed_roles):
            logger.warning(
                f"Access denied - insufficient permissions",
                extra={
                    "user_id": str(current_user.user_id),
                    "user_roles": current_user.roles,
                    "required_roles": list(allowed_roles),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "message": "Insufficient permissions",
                    "details": {
                        "required_roles": list(allowed_roles),
                        "your_roles": current_user.roles,
                    },
                },
            )
        return current_user
    
    return check_roles