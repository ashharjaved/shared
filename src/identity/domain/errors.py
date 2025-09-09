# src/identity/domain/errors.py
"""Domain exception hierarchy."""

from typing import Any


class DomainError(Exception):
    """Base class for all domain errors."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(DomainError):
    """Raised when domain validation rules are violated."""
    pass


class InvariantViolation(DomainError):
    """Raised when domain invariants are violated."""
    pass


class UnauthorizedDomainAction(DomainError):
    """Raised when user lacks permission for domain action."""
    pass


class ConflictError(DomainError):
    """Raised when operation conflicts with existing state."""
    pass


class NotFoundInDomain(DomainError):
    """Raised when required domain entity is not found."""
    pass