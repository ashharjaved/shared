from __future__ import annotations

from typing import List, Optional, Tuple
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared.logging import bind_request_context, clear_request_context
from src.shared.utils import tenant_ctxvars as ctxvars

# Canonical headers used *only as fallback* if Authorization/JWT isn't wired yet
TENANT_ID_HEADER = "X-Tenant-Id"
USER_ID_HEADER   = "X-User-Id"
ROLES_HEADER     = "X-Roles"        # CSV list: "TENANT_ADMIN,STAFF"

def _extract_claims(request: Request) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Extract (tenant_id, user_id, roles[]) from:
      1) prior auth middleware via request.state (preferred),
      2) fallback headers (for early bootstrapping / internal calls).
    """
    tenant_id: Optional[str] = getattr(request.state, "tenant_id", None) or request.headers.get(TENANT_ID_HEADER)
    user_id:   Optional[str] = getattr(request.state, "user_id", None)   or request.headers.get(USER_ID_HEADER)
    roles_csv: str = getattr(request.state, "roles_csv", "") or request.headers.get(ROLES_HEADER, "") or ""
    roles: List[str] = [r.strip() for r in roles_csv.split(",") if r.strip()]
    return tenant_id, user_id, roles

class ContextMiddleware(BaseHTTPMiddleware):
    """
    Binds request-scoped identity to:
      - ctxvars (tenant_id, user_id, roles, request_id)
      - structured log MDC via bind_request_context
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            tenant_id, user_id, roles = _extract_claims(request)
            request_id = getattr(request.state, "request_id", None)

            # 1) ctxvars for DB layer & anywhere else
            ctxvars.set_all(tenant_id=tenant_id, user_id=user_id, roles=roles, request_id=request_id)

            # 2) attach to logs (structlog MDC)
            bind_request_context(
                request_id=request_id or "",
                tenant_id=tenant_id or "",
                user_id=user_id or "",
                roles=",".join(roles) if roles else "",
            )

            response = await call_next(request)
            return response
        finally:
            clear_request_context()
            ctxvars.clear_all()
