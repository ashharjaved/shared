from __future__ import annotations
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared.structured_logging import get_logger
from src.shared.http.responses import error_response
from src.shared.errors import DomainError, ErrorCode

logger = get_logger("http")

class ExceptionMiddleware(BaseHTTPMiddleware):
    """
    Centralized error translation to the platform's error contract.
    Never leaks stack traces; always returns {code, message, details} JSON.
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = (
            getattr(request.state, "request_id", None) 
            or request.headers.get("X-Request-Id") 
            or str(uuid.uuid4())
        )
        
        if not hasattr(request.state, "request_id"):
            request.state.request_id = request_id

        try:
            return await call_next(request)
        except DomainError as ae:
            logger.warning(
                "app_error",
                code=ae.code,
                message=ae.message,
                status=ae.http_status,
                request_id=request_id,
            )
            return error_response(ae, correlation_id=request_id)
        except Exception as e:
            logger.exception(
                "unhandled_exception", 
                exc_info=e, 
                request_id=request_id
            )
            err = DomainError(
                code=ErrorCode.INTERNAL_ERROR, 
                message="Internal error", 
                http_status=500
            )
            return error_response(err, correlation_id=request_id)