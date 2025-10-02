"""
Correlation ID Middleware
Adds unique request ID for distributed tracing
"""
from __future__ import annotations

import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from shared.infrastructure.observability.logger import bind_context, clear_context, get_logger

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation/trace ID to all requests.
    
    Generates or extracts X-Request-ID header and binds it to logging context.
    All logs within the request will include this trace_id for correlation.
    
    Also measures request duration and adds it to response headers.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """
        Process request with correlation ID.
        
        Args:
            request: Incoming FastAPI request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response with correlation ID header
        """
        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Request-ID")
        if not correlation_id:
            correlation_id = str(uuid4())
        
        # Bind to logging context
        bind_context(
            trace_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )
        
        # Record start time
        start_time = time.time()
        
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
            },
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Add headers
            response.headers["X-Request-ID"] = correlation_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            
            logger.info(
                "Request completed",
                extra={
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            
            return response
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.error(
                "Request failed",
                extra={
                    "error": str(e),
                    "duration_ms": duration_ms,
                },
                exc_info=True,
            )
            raise
        finally:
            # Clear logging context
            clear_context()