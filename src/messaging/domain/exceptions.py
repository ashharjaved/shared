# src/messaging/domain/exceptions.py

"""Domain exceptions for messaging module."""


from identity.domain.types import TenantId


class DomainError(Exception):
    """Base domain exception."""
    
    def __init__(self, message: str, code: str = "domain_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(DomainError):
    """Domain validation failed."""
    
    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message, "validation_error")


class InvariantViolation(DomainError):
    """Business invariant violated."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "invariant_violation")


class UnauthorizedDomainAction(DomainError):
    """Action not permitted in current domain state."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "unauthorized_action")


class ConflictError(DomainError):
    """Domain entity conflict (e.g., duplicate key)."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "conflict_error")


class NotFoundInDomain(DomainError):
    """Required domain entity not found."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "not_found")


class QuotaExceeded(DomainError):
    """Tenant quota limit exceeded."""
    
    def __init__(self, message: str, tenant_id: 'TenantId') -> None:
        self.tenant_id = tenant_id
        super().__init__(message, "quota_exceeded")


class RateLimited(DomainError):
    """Rate limit exceeded for tenant or channel."""
    
    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, "rate_limited")


class InvalidMessageTransition(InvariantViolation):
    """Illegal message status state transition."""
    
    def __init__(self, from_status: str, to_status: str) -> None:
        message = f"Invalid transition from {from_status} to {to_status}"
        super().__init__(message)

class WhatsAppDomainException(Exception):
    """Base exception for WhatsApp domain errors"""
    pass

class InvalidCredentialsException(WhatsAppDomainException):
    """Invalid WhatsApp credentials"""
    pass

class ChannelNotFoundException(WhatsAppDomainException):
    """WhatsApp channel not found"""
    pass

class MessageNotFoundException(WhatsAppDomainException):
    """WhatsApp message not found"""
    pass

class RateLimitExceededException(WhatsAppDomainException):
    """Rate limit exceeded for WhatsApp API"""
    pass

class InvalidWebhookSignatureException(WhatsAppDomainException):
    """Invalid webhook signature"""
    pass