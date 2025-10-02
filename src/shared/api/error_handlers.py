"""
Centralized API Error Handlers
Maps exceptions to standard error responses
"""
from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

from shared.api.response_models import ErrorDetail, ErrorResponse
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


# Standard error codes
class ErrorCode:
    """Standard error codes for the platform."""
    
    # Client errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    UNPROCESSABLE_ENTITY = "UNPROCESSABLE_ENTITY"
    
    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    
    # Business errors
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    DUPLICATE_ENTITY = "DUPLICATE_ENTITY"
    INVALID_STATE = "INVALID_STATE"


class APIException(Exception):
    """
    Base exception for API errors.
    
    Attributes:
        code: Error code
        message: Error message
        status_code: HTTP status code
        details: Additional error details
    """
    
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class ValidationException(APIException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class NotFoundException(APIException):
    """Raised when requested resource not found."""
    
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedException(APIException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(APIException):
    """Raised when user lacks permissions."""
    
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictException(APIException):
    """Raised when operation conflicts with existing state."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=ErrorCode.CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class BusinessRuleViolationException(APIException):
    """Raised when business rule violated."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=ErrorCode.BUSINESS_RULE_VIOLATION,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    Handle APIException and subclasses.
    
    Args:
        request: FastAPI request
        exc: APIException instance
        
    Returns:
        JSONResponse with error details
    """
    logger.warning(
        f"API exception: {exc.code}",
        extra={
            "code": exc.code,
            "message": exc.message,
            "status_code": exc.status_code,
            "path": str(request.url),
        },
    )
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    Args:
        request: FastAPI request
        exc: Unexpected exception
        
    Returns:
        JSONResponse with generic error
    """
    logger.error(
        "Unhandled exception",
        extra={
            "error": str(exc),
            "type": exc.__class__.__name__,
            "path": str(request.url),
        },
        exc_info=True,
    )
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="An internal error occurred. Please try again later.",
            details=None,  # Never expose internal details in production
        )
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )