from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared.structured_logging import bind_request_context

REQUEST_ID_HEADER = "X-Request-ID"

class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request is tagged with a stable correlation id.
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = (
            request.headers.get(REQUEST_ID_HEADER) 
            or str(uuid.uuid4())
        )
        request.state.request_id = request_id

        # Bind to structured logging
        bind_request_context(request_id=request_id)

        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            # Cleanup is handled by ContextMiddleware
            pass