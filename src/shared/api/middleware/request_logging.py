"""
Request Logging Middleware
Logs request/response details for observability
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log request and response details.
    
    Logs:
    - Request method, path, client IP
    - Response status code, duration
    - Correlation ID if present
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and log details"""
        
        # Start timer
        start_time = time.time()
        
        # Get client info
        client_ip = request.client.host if request.client else None
        correlation_id = getattr(request.state, "correlation_id", None)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log successful request
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                    "correlation_id": correlation_id,
                },
            )
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"{request.method} {request.url.path} - ERROR",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                    "correlation_id": correlation_id,
                },
            )
            
            # Re-raise exception
            raise