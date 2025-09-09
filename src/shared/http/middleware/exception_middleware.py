from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.shared.logging import get_logger
from src.shared.http.responses import error_response
from src.shared.errors import DomainError, ExternalServiceError  # your standardized exceptions

class ExceptionMiddleware(BaseHTTPMiddleware):
    """
    Centralized error translation to the platform's error contract.
    Never leaks stack traces; always returns {code, message, details} JSON.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        log = get_logger("http")
        request_id = getattr(request.state, "request_id", None)
        try:
            return await call_next(request)
        except DomainError as ae:
            # Domain/expected errors — warn, with structured context
            log.warning(
                "app_error",
                code=ae.code,
                message=ae.message,
                status=ae.http_status,
                request_id=request_id,
            )
            return error_response(ae, correlation_id=request_id)
        except Exception:
            # Unexpected — log full exception but return generic 500 to client
            log.exception("unhandled_exception", request_id=request_id)
            err = ExternalServiceError(message="Internal error")
            return error_response(err, correlation_id=request_id)
