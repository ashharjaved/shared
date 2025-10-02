from __future__ import annotations

from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.shared_.database.database import get_session_factory
from src.shared_.http.public_paths import is_public_path
from src.shared_.utils.tenant_ctxvars import set_all, clear_all
from src.shared_.errors import UnauthorizedError

import structlog
logger = structlog.get_logger()

class RlsMiddleware(BaseHTTPMiddleware):
    """
    Row Level Security middleware - enforces tenant context.
    """
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Skip public endpoints
        if is_public_path(path) or any(
            path.startswith(prefix) 
            for prefix in ["/docs", "/openapi", "/_health", "/favicon.ico"]
        ):
            return await call_next(request)

        # Check if context is already set by ContextMiddleware
        from src.shared_.utils import tenant_ctxvars as ctxvars
        tenant_id = ctxvars.TENANT_ID_VAR.get()
        
        if tenant_id:
            # Context already established - proceed
            logger.debug(
                "RLS context already set",
                tenant_id=tenant_id,
                path=path
            )
            # Context is already set, proceed
            return await call_next(request)
        
        # Try to extract from JWT if context wasn't set
        claims = getattr(request.state, "user_claims", None)
        if not isinstance(claims, dict):
            logger.warning("RLS failed - no claims or context", method=request.method, path=path)
            raise UnauthorizedError(message="Authentication required")

        tenant_id = (
            claims.get("tenant_id") 
            or claims.get("tid") 
            or getattr(request.state, "tenant_id", None)
        )
        user_id = claims.get("sub") or getattr(request.state, "user_id", None)
        roles = claims.get("roles") or getattr(request.state, "role", []) or []

        # Enforce tenant context
        if not tenant_id:
            raise UnauthorizedError(message="Missing tenant context")

        # Set context variables
        set_all(
            tenant_id=str(tenant_id), 
            user_id=str(user_id) if user_id else None, 
            roles=roles, 
            request_id=getattr(request.state, "request_id", None)
        )
        # CRITICAL: Execute GUC commands on database session
        # This ensures RLS policies are enforced at the database level
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                # Set session-local GUC variables for RLS
                await session.execute(
                    text("SELECT set_config('app.jwt_tenant', :tenant, true)"),
                    {"tenant": str(tenant_id)},
                )
                await session.execute(
                    text("SELECT set_config('app.user_id', :user, true)"),
                    {"user": str(user_id) if user_id else ""},
                )
                await session.execute(
                    text("SELECT set_config('app.roles', :roles, true)"),
                    {"roles": roles},
                )
                
                logger.info(
                    "RLS context established",
                    tenant_id=str(tenant_id),
                    user_id=str(user_id) if user_id else None,
                    roles=roles,
                    path=path,
                )
        
        except Exception as e:
            logger.error(
                "Failed to set RLS GUC",
                error=str(e),
                tenant_id=str(tenant_id),
                path=path,
            )
            clear_all()
            raise UnauthorizedError(message="Failed to establish tenant context")

        try:
            response = await call_next(request)
            return response
        finally:
            clear_all()
            logger.debug("RLS context cleared", path=path)