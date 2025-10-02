from __future__ import annotations

from typing import List, Optional, Tuple
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from src.shared_.structured_logging import bind_request_context
from src.shared_.utils import tenant_ctxvars as ctxvars

import structlog
logger = structlog.get_logger()

# Fallback headers (used only if JwtAuth didn't populate request.state)
TENANT_ID_HEADER = "X-Tenant-Id"
USER_ID_HEADER = "X-User-Id"
ROLES_HEADER = "X-Roles"  # CSV: "TENANT_ADMIN,STAFF"

def _extract_claims(request: Request) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Extract (tenant_id, user_id, roles[]) from:
      1) request.state (preferred; set by JwtAuthMiddleware)
      2) fallback headers (bootstrapping/internal calls)
    """
    tenant_id = (
        getattr(request.state, "tenant_id", None) 
        or request.headers.get(TENANT_ID_HEADER)
    )
    user_id = (
        getattr(request.state, "user_id", None) 
        or request.headers.get(USER_ID_HEADER)
    )
    roles_csv = (
        getattr(request.state, "roles", "") 
        or request.headers.get(ROLES_HEADER, "") 
        or ""
    )
    roles = [r.strip() for r in roles_csv.split(",") if r.strip()]
    return tenant_id, user_id, roles

class ContextMiddleware(BaseHTTPMiddleware):
    """
    Binds request-scoped identity to:
      - ctxvars (tenant_id, user_id, roles, request_id)
      - structlog MDC via bind_request_context
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            tenant_id, user_id, roles = _extract_claims(request)
            request_id = (
                getattr(request.state, "request_id", None) 
                or request.headers.get("X-Request-Id")
            )
            
            # Ensure request.state has request_id for other middlewares
            if not hasattr(request.state, "request_id"):
                request.state.request_id = request_id

            # Set ctxvars for DB layer & anywhere else
            ctxvars.set_all(
                tenant_id=tenant_id, 
                user_id=user_id, 
                roles=roles, 
                request_id=request_id
            )

            # Attach to logs (structlog MDC)
            bind_request_context(
                request_id=request_id or "",
                tenant_id=tenant_id or "",
                user_id=user_id or "",
                roles=",".join(roles) if roles else "",
            )

            logger.debug(
                "ContextMiddleware bound context",
                request_id=request_id, 
                tenant_id=tenant_id, 
                user_id=user_id, 
                roles=roles
            )

            response = await call_next(request)
            return response
        finally:
            logger.debug(
                "Context cleared", 
                request_id=getattr(request.state, "request_id", None)
            )
            #clear_request_context()
            #ctxvars.clear_all()