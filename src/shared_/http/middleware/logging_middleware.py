from __future__ import annotations

import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared_.structured_logging import get_logger, bind_request_context

logger = get_logger("http")

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured access logs + lightweight audit hooks.
    Logs start & end with latency, method, path, status.
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        
        # Bind basic request info
        bind_request_context(
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            
            # Log successful request
            logger.info(
                "http_access",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=request.client.host if request.client else None,
            )
            
            return response
            
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            
            # Log failed request
            logger.error(
                "http_error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                client_ip=request.client.host if request.client else None,
                error=str(e),
            )
            
            raise