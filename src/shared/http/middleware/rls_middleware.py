from __future__ import annotations

from typing import Iterable
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared.errors import RlsNotSetError
from src.shared.utils import tenant_ctxvars as ctxvars

class RlsContextEnforcerMiddleware(BaseHTTPMiddleware):
    """
    Enforces presence of tenant context for tenant-scoped APIs to uphold RLS guarantees.

    - For PUBLIC_PATHS (health/docs/webhook verify etc.), skip enforcement.
    - Otherwise, ensure ctxvars.tenant_id exists; else raise RlsNotSetError (mapped to 400/403).
    """
    def __init__(self, app, public_paths: Iterable[str] | None = None):
        super().__init__(app)
        self.public_paths = set(public_paths or ["/", "/docs", "/openapi.json", "/_health/db", "/_health/redis", "/api/messaging/webhook"])

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if any(path == p or path.startswith(p.rstrip("/") + "/") for p in self.public_paths):
            return await call_next(request)

        tenant_id = ctxvars.TENANT_ID_VAR.get()
        if not tenant_id:
            # Fail fast; repositories will rely on GUC from ctxvars
            raise RlsNotSetError(message="Tenant context not set for tenant-scoped endpoint")

        return await call_next(request)
