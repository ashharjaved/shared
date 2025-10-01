"""Standardized error responses."""

from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid


class ErrorResponse(BaseModel):
    """Standard error response format."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> dict:
    """Create standardized error response."""
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "correlation_id": str(uuid.uuid4())
    }


# Standard error codes
ERROR_CODES = {
    400: "validation_error",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "invalid_request",
    429: "rate_limited",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable"
}