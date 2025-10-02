"""
Identity Domain Exceptions
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


class IdentityDomainException(Exception):
    """Base exception for identity domain"""
    pass


class InvalidCredentialsException(IdentityDomainException):
    """Raised when credentials are invalid"""
    
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class AccountLockedException(IdentityDomainException):
    """Raised when account is locked due to failed attempts"""
    
    def __init__(self, unlock_at: Optional[datetime] = None) -> None:
        self.unlock_at = unlock_at
        message = "Account is locked"
        if unlock_at:
            message = f"Account is locked until {unlock_at.isoformat()}"
        super().__init__(message)


class EmailNotVerifiedException(IdentityDomainException):
    """Raised when operation requires verified email"""
    
    def __init__(self) -> None:
        super().__init__("Email address must be verified")


class DuplicateEmailException(IdentityDomainException):
    """Raised when email already exists"""
    
    def __init__(self, email: str) -> None:
        super().__init__(f"Email already registered: {email}")


class DuplicateSlugException(IdentityDomainException):
    """Raised when organization slug already exists"""
    
    def __init__(self, slug: str) -> None:
        super().__init__(f"Organization slug already exists: {slug}")


class OrganizationNotFoundException(IdentityDomainException):
    """Raised when organization not found"""
    
    def __init__(self, org_id: str) -> None:
        super().__init__(f"Organization not found: {org_id}")


class UserNotFoundException(IdentityDomainException):
    """Raised when user not found"""
    
    def __init__(self, user_id: str) -> None:
        super().__init__(f"User not found: {user_id}")


class RoleNotFoundException(IdentityDomainException):
    """Raised when role not found"""
    
    def __init__(self, role_id: str) -> None:
        super().__init__(f"Role not found: {role_id}")


class PermissionDeniedException(IdentityDomainException):
    """Raised when operation is not permitted"""
    
    def __init__(self, message: str = "Operation not permitted") -> None:
        super().__init__(message)


class RefreshTokenExpiredException(IdentityDomainException):
    """Raised when refresh token has expired"""
    
    def __init__(self) -> None:
        super().__init__("Refresh token has expired")


class RefreshTokenRevokedException(IdentityDomainException):
    """Raised when refresh token has been revoked"""
    
    def __init__(self) -> None:
        super().__init__("Refresh token has been revoked")


class ApiKeyExpiredException(IdentityDomainException):
    """Raised when API key has expired"""
    
    def __init__(self) -> None:
        super().__init__("API key has expired")


class ApiKeyRevokedException(IdentityDomainException):
    """Raised when API key has been revoked"""
    
    def __init__(self) -> None:
        super().__init__("API key has been revoked or deactivated")

class DuplicateRoleNameException(IdentityDomainException):
    """Raised when role name already exists in organization"""
    
    def __init__(self, name: str) -> None:
        super().__init__(f"Role name already exists: {name}")

class SystemRoleModificationException(IdentityDomainException):
    """Raised when attempting to modify a system role"""
    
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Cannot modify system role: {role_name}")

class PasswordResetTokenAlreadyUsedException(IdentityDomainException):
    """Raised when attempting to modify a system role"""
    
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Cannot modify system role: {role_name}")

class PasswordResetTokenExpiredException(IdentityDomainException):
    """Raised when attempting to modify a system role"""
    
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Cannot modify system role: {role_name}")

class EmailVerificationTokenExpiredException(IdentityDomainException):
    """Raised when attempting to modify a system role"""
    
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Cannot modify system role: {role_name}")

class EmailVerificationTokenAlreadyUsedException(IdentityDomainException):
    """Raised when attempting to modify a system role"""
    
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Cannot modify system role: {role_name}")

class ValidationError(IdentityDomainException):
    """Raised when attempting to modify a system role"""
    
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Cannot modify system role: {role_name}")