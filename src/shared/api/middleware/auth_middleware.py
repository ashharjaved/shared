"""
Authentication Middleware
JWT validation and user context binding
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from shared.api.error_handlers import UnauthorizedException
from shared.infrastructure.observability.logger import bind_context, get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for JWT authentication and user context binding.
    
    PLACEHOLDER: This is a simplified implementation.
    Full JWT validation will be implemented in DEV-1 Identity module.
    
    Validates JWT tokens and binds user/tenant context for:
    - Logging (user_id, tenant_id in all logs)
    - RLS enforcement (via RLSManager)
    - Authorization checks
    
    Attributes:
        excluded_paths: Paths that don't require authentication
    """
    
    def __init__(
        self,
        app: Any,
        excluded_paths: list[str] | None = None,
    ) -> None:
        """
        Initialize auth middleware.
        
        Args:
            app: FastAPI application
            excluded_paths: List of path prefixes to exclude from auth
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
        ]
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """
        Validate JWT and bind user context.
        
        Args:
            request: Incoming FastAPI request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response from endpoint
            
        Raises:
            UnauthorizedException: If token invalid or missing
        """
        # Check if path is excluded
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise UnauthorizedException("Missing or invalid authorization header")
        
        token = auth_header.replace("Bearer ", "")
        
        try:
            # PLACEHOLDER: Validate JWT and extract claims
            # This will be implemented in DEV-1 Identity module
            user_context = await self._validate_token(token)
            
            # Bind user context to logging
            bind_context(
                user_id=user_context["user_id"],
                tenant_id=user_context["organization_id"],
                roles=user_context.get("roles", []),
            )
            
            # Store in request state for access in endpoints
            request.state.user_id = user_context["user_id"]
            request.state.organization_id = user_context["organization_id"]
            request.state.roles = user_context.get("roles", [])
            
            logger.debug(
                "User authenticated",
                extra={
                    "user_id": user_context["user_id"],
                    "organization_id": user_context["organization_id"],
                },
            )
            
            return await call_next(request)
        except Exception as e:
            logger.warning(
                "Authentication failed",
                extra={"error": str(e)},
            )
            raise UnauthorizedException("Invalid or expired token")
    
    async def _validate_token(self, token: str) -> dict[str, Any]:
        """
        Validate JWT token and extract claims.
        
        PLACEHOLDER: This will be implemented in DEV-1 Identity module
        with proper JWT validation using PyJWT.
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary with user claims (user_id, organization_id, roles)
            
        Raises:
            Exception: If token invalid
        """
        # PLACEHOLDER: Return mock data for now
        # Real implementation will:
        # 1. Decode JWT with secret key
        # 2. Verify signature
        # 3. Check expiration
        # 4. Extract claims
        
        logger.warning("Using placeholder JWT validation - implement in DEV-1")
        
        return {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "organization_id": "00000000-0000-0000-0000-000000000000",
            "roles": ["user"],
        }