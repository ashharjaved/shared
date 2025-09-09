from __future__ import annotations

import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared.logging import get_logger, bind_request_context, set_correlation_id

log = get_logger("http")

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured access logs + lightweight audit hooks.
    - Logs start & end with latency, method, path, status.
    - Context (request_id/tenant_id/user_id) is already bound by ContextMiddleware.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        # best-effort: bind basic request info (path/method) without leaking PII
        cid = request.headers.get("x-correlation-id")
        set_correlation_id(cid)
        bind_request_context(
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else None,
            )        
        try:
            response = await call_next(request)
            return response
        finally:
            dur_ms = round((time.perf_counter() - start) * 1000.0, 2)
            status = getattr(request.state, "response_status", None)  # optional
            log.info(
                "http_access",
                method=request.method,
                path=request.url.path,
                status_code=status or getattr(request, "status_code", None),
                duration_ms=dur_ms,
            )
