# src/shared/errors.py
"""Exception hierarchy for the WhatsApp SaaS platform."""

import uuid
from typing import Any, Dict, Optional, List
from enum import Enum
from typing import Optional

from enum import Enum
from typing import Dict

class ErrorCode(str, Enum):
    """Standard error codes for API responses."""
    
    # 4xx Client Errors
    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    INVALID_CREDENTIALS = "invalid_credentials"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMITED = "rate_limited"
    EXTERNAL_ERROR = "external_error"
    # 5xx Server Errors  
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT_ERROR = "timeout_error"
    
    # Domain-specific errors
    RLS_NOT_SET = "rls_not_set"
    TENANT_LIMIT_EXCEEDED = "tenant_limit_exceeded"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    INVALID_TOKEN = "invalid_token"
    TOKEN_EXPIRED = "token_expired"
    REFRESH_TOKEN_REUSED = "refresh_token_reused"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    PROVIDER_ERROR = "provider_error"

ERROR_CODES: Dict[ErrorCode, Dict[str, str | int]] = {
    ErrorCode.VALIDATION_ERROR: {"http": 422, "code": "validation_error"},
    ErrorCode.UNAUTHORIZED: {"http": 401, "code": "unauthorized"},
    ErrorCode.INVALID_CREDENTIALS: {"http": 401, "code": "invalid_credentials"},
    ErrorCode.FORBIDDEN: {"http": 403, "code": "forbidden"},
    ErrorCode.NOT_FOUND: {"http": 404, "code": "not_found"},
    ErrorCode.CONFLICT: {"http": 409, "code": "conflict"},
    ErrorCode.IDEMPOTENCY_CONFLICT: {"http": 409, "code": "idempotency_conflict"},
    ErrorCode.INVALID_REQUEST: {"http": 422, "code": "invalid_request"},
    ErrorCode.RATE_LIMITED: {"http": 429, "code": "rate_limited"},
    ErrorCode.EXTERNAL_ERROR: {"http": 502, "code": "external_error"},
    ErrorCode.INTERNAL_ERROR: {"http": 500, "code": "internal_error"},
    ErrorCode.SERVICE_UNAVAILABLE: {"http": 503, "code": "service_unavailable"},
    ErrorCode.TIMEOUT_ERROR: {"http": 504, "code": "timeout_error"},
    ErrorCode.RLS_NOT_SET: {"http": 403, "code": "rls_not_set"},
    ErrorCode.TENANT_LIMIT_EXCEEDED: {"http": 403, "code": "tenant_limit_exceeded"},
    ErrorCode.SUBSCRIPTION_EXPIRED: {"http": 403, "code": "subscription_expired"},
    ErrorCode.INVALID_TOKEN: {"http": 401, "code": "invalid_token"},
    ErrorCode.TOKEN_EXPIRED: {"http": 401, "code": "token_expired"},
    ErrorCode.REFRESH_TOKEN_REUSED: {"http": 401, "code": "refresh_token_reused"},
    ErrorCode.BUSINESS_RULE_VIOLATION: {"http": 422, "code": "business_rule_violation"},
    ErrorCode.PROVIDER_ERROR: {"http": 502, "code": "provider_error"},
}

class DomainError(Exception):
    """Base exception for all domain errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        http_status: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.correlation_id = correlation_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.http_status = http_status

    def to_payload(self, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "code": self.code.value,  # Use .value to get the string value of the enum
            "message": self.message,
        }
        if correlation_id:
            payload["correlation_id"] = correlation_id
        return payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        result = {
            "code": self.code.value,
            "message": self.message,
        }
        
        if self.details:
            result["details"] = str(self.details)
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
            
        return result


class ValidationError(DomainError):
    """Validation failed on input data."""
    
    def __init__(
        self,
        message: str,
        field_errors: Optional[Dict[str, List[str]]] = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.VALIDATION_ERROR,
            details={"field_errors": field_errors} if field_errors else None,
            **kwargs
        )
        self.field_errors = field_errors or {}


class NotFoundError(DomainError):
    """Requested resource was not found."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        message = f"{resource_type} not found"
        if resource_id:
            message += f" with ID: {resource_id}"
        
        super().__init__(
            message,
            ErrorCode.NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id},
            **kwargs
        )


class ConflictError(DomainError):
    """Resource already exists or conflicts with current state."""
    
    def __init__(
        self,
        message: str,
        conflict_field: Optional[str] = None,
        existing_value: Optional[str] = None,
        **kwargs
    ):
        details = {}
        if conflict_field:
            details["conflict_field"] = conflict_field
        if existing_value:
            details["existing_value"] = existing_value
            
        super().__init__(
            message,
            ErrorCode.CONFLICT,
            details=details if details else None,
            **kwargs
        )


class AuthenticationError(DomainError):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message,
            ErrorCode.UNAUTHORIZED,
            **kwargs
        )

class UnauthorizedError(DomainError):
    """Unauthorized Error"""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message,
            ErrorCode.UNAUTHORIZED,
            **kwargs
        )

class InvalidCredentialsError(DomainError):
    """Invalid username/password combination."""
    
    def __init__(self, message: str = "Invalid credentials", **kwargs):
        super().__init__(
            message,
            ErrorCode.INVALID_CREDENTIALS,
            **kwargs
        )


class AuthorizationError(DomainError):
    """User does not have permission to perform this action."""
    
    def __init__(
        self,
        message: str = "Access forbidden",
        required_role: Optional[str] = None,
        user_roles: Optional[List[str]] = None,
        **kwargs
    ):
        details = {}
        if required_role:
            details["required_role"] = required_role
        if user_roles:
            details["user_roles"] = user_roles
            
        super().__init__(
            message,
            ErrorCode.FORBIDDEN,
            details=details if details else None,
            **kwargs
        )


class RateLimitError(DomainError):
    """Rate limit exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit_type: Optional[str] = None,
        **kwargs
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        if limit_type:
            details["limit_type"] = limit_type
            
        super().__init__(
            message,
            ErrorCode.RATE_LIMITED,
            details=details if details else None,
            **kwargs
        )


class RlsNotSetError(DomainError):
    """Row Level Security context not properly set."""
    
    def __init__(
        self,
        message: str = "RLS context not set - tenant_id required",
        missing_context: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.RLS_NOT_SET,
            details={"missing_context": missing_context} if missing_context else None,
            **kwargs
        )


class BusinessRuleViolationError(DomainError):
    """Business rule or invariant was violated."""
    
    def __init__(
        self,
        message: str,
        rule_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.BUSINESS_RULE_VIOLATION,
            details={"rule_name": rule_name} if rule_name else None,
            **kwargs
        )


class IdempotencyConflictError(DomainError):
    """Idempotency key conflict detected."""
    
    def __init__(
        self,
        message: str = "Idempotency conflict - request already processed",
        idempotency_key: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.IDEMPOTENCY_CONFLICT,
            details={"idempotency_key": idempotency_key} if idempotency_key else None,
            **kwargs
        )


class InvalidTokenError(DomainError):
    """JWT token is invalid."""
    
    def __init__(
        self,
        message: str = "Invalid token",
        token_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.INVALID_TOKEN,
            details={"token_type": token_type} if token_type else None,
            **kwargs
        )


class TokenExpiredError(DomainError):
    """JWT token has expired."""
    
    def __init__(
        self,
        message: str = "Token expired",
        token_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.TOKEN_EXPIRED,
            details={"token_type": token_type} if token_type else None,
            **kwargs
        )


class RefreshTokenReusedError(DomainError):
    """Refresh token was reused (security violation)."""
    
    def __init__(
        self,
        message: str = "Refresh token reused - token family invalidated",
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.REFRESH_TOKEN_REUSED,
            **kwargs
        )


class SubscriptionExpiredError(DomainError):
    """Tenant subscription has expired."""
    
    def __init__(
        self,
        message: str = "Subscription expired",
        tenant_id: Optional[uuid.UUID] = None,
        expired_at: Optional[str] = None,
        **kwargs
    ):
        details = {}
        if expired_at:
            details["expired_at"] = expired_at
            
        super().__init__(
            message,
            ErrorCode.SUBSCRIPTION_EXPIRED,
            details=details if details else None,
            tenant_id=tenant_id,
            **kwargs
        )


class TenantLimitExceededError(DomainError):
    """Tenant has exceeded their plan limits."""
    
    def __init__(
        self,
        message: str,
        limit_type: str,
        current_usage: int,
        limit_value: int,
        **kwargs
    ):
        super().__init__(
            message,
            ErrorCode.TENANT_LIMIT_EXCEEDED,
            details={
                "limit_type": limit_type,
                "current_usage": current_usage,
                "limit_value": limit_value,
            },
            **kwargs
        )


class ProviderError(DomainError):
    """External provider (WhatsApp, etc.) returned an error."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        provider_code: Optional[str] = None,
        provider_message: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = {"provider": provider}
        if provider_code:
            details["provider_code"] = provider_code
        if provider_message:
            details["provider_message"] = provider_message
        if retry_after:
            details["retry_after"] = str(retry_after)
            
        super().__init__(
            message,
            ErrorCode.PROVIDER_ERROR,
            details=details,
            **kwargs
        )

class ExternalError(DomainError):
    """
    Error for failures caused by external systems (e.g., WhatsApp API, Redis, SMTP).
    Unlike other errors, this does not require multiple params.
    """

    def __init__(self, message: str):
        super().__init__(code=ErrorCode.EXTERNAL_ERROR, message=message)


class TimeoutError(DomainError):
    """Operation timed out."""
    
    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        if operation:
            details["operation"] = operation
            
        super().__init__(
            message,
            ErrorCode.TIMEOUT_ERROR,
            details=details if details else None,
            **kwargs
        )