from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars
import structlog

# Prefer consistent canonical header names across services
REQUEST_ID_HEADER = "X-Request-ID"

def clear_request_context() -> None:
    """Clear all bound contextvars (call at end of request/worker job)."""
    structlog.contextvars.clear_contextvars()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request is tagged with a stable correlation id.
    - Accepts inbound X-Request-ID or generates UUID4.
    - Echoes X-Request-ID on the response.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
            response.headers.setdefault(REQUEST_ID_HEADER, request_id)
            return response
        finally:
            clear_request_context()