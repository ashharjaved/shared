from __future__ import annotations

"""
Domain-level exception hierarchy for Identity & Access.

These exceptions subclass the shared exception classes so they continue to map
to the standardized error contract, while providing domain semantics that are
useful in tests and application policies.
"""

from src.shared.exceptions import (
    AppError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    InvalidCredentialsError,
    RateLimitedError,
)


class DomainError(AppError):
    """Base for all domain exceptions in Identity context."""


class TenantNotFoundError(DomainError, NotFoundError):
    """Raised when a tenant is missing or inactive."""


class UserInactiveError(DomainError, UnauthorizedError):
    """Raised when a user exists but is inactive (disabled/suspended)."""


class InvalidCredentialsDomainError(DomainError, InvalidCredentialsError):
    """Raised when credentials are invalid in the login flow."""


class AccountLockedError(DomainError, RateLimitedError):
    """Raised when account is temporarily locked due to too many failed attempts."""


class EmailConflictError(DomainError, ConflictError):
    """Raised when (tenant_id, email) violates uniqueness constraint."""


class RoleForbiddenError(DomainError, ForbiddenError):
    """Raised when user role is insufficient for an operation."""
