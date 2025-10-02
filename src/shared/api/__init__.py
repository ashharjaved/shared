"""
Shared API Layer
FastAPI routers, response models, error handlers, and middleware
"""
from shared.api.base_router import create_api_router
from shared.api.error_handlers import (
    APIException,
    BusinessRuleViolationException,
    ConflictException,
    ErrorCode,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
    api_exception_handler,
    generic_exception_handler,
)
from shared.api.middleware import (
    AuthMiddleware,
    CorrelationIdMiddleware,
    RateLimitMiddleware,
)
from shared.api.response_models import (
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    SuccessResponse,
)

__all__ = [
    # Router
    "create_api_router",
    # Response models
    "SuccessResponse",
    "ErrorResponse",
    "ErrorDetail",
    "PaginatedResponse",
    # Exceptions
    "APIException",
    "ValidationException",
    "NotFoundException",
    "UnauthorizedException",
    "ForbiddenException",
    "ConflictException",
    "BusinessRuleViolationException",
    "ErrorCode",
    # Error handlers
    "api_exception_handler",
    "generic_exception_handler",
    # Middleware
    "AuthMiddleware",
    "CorrelationIdMiddleware",
    "RateLimitMiddleware",
]