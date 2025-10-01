# src/identity/domain/events/auth_events.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.identity.domain.types import UserId, TenantId


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    timestamp: datetime
    event_id: str
    
    def to_dict(self) -> dict:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.__class__.__name__,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class UserLoggedIn(DomainEvent):
    """
    Event raised when user successfully authenticates.
    
    Used for:
    - Audit logging
    - Security monitoring
    - Analytics
    """
    user_id: UserId
    tenant_id: TenantId
    email: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
            "email": self.email,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        })
        return base


@dataclass(frozen=True)
class UserLoginFailed(DomainEvent):
    """
    Event raised when authentication fails.
    
    Reasons:
    - user_not_found: Email doesn't exist
    - invalid_password: Password mismatch
    - user_inactive: Account deactivated
    - account_locked: Too many failed attempts
    """
    email: str
    tenant_id: TenantId
    reason: str  # See reasons above
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "email": self.email,
            "tenant_id": str(self.tenant_id),
            "reason": self.reason,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        })
        return base


@dataclass(frozen=True)
class UserLoggedOut(DomainEvent):
    """Event raised when user logs out."""
    user_id: UserId
    tenant_id: TenantId
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
        })
        return base


@dataclass(frozen=True)
class UserRoleChanged(DomainEvent):
    """
    Event raised when user's role is modified.
    
    Critical for:
    - Compliance auditing
    - Security monitoring
    - Access control tracking
    """
    user_id: UserId
    tenant_id: TenantId
    old_role: str
    new_role: str
    changed_by: UserId
    reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
            "old_role": self.old_role,
            "new_role": self.new_role,
            "changed_by": str(self.changed_by),
            "reason": self.reason,
        })
        return base


@dataclass(frozen=True)
class UserCreated(DomainEvent):
    """Event raised when new user is created."""
    user_id: UserId
    tenant_id: TenantId
    email: str
    role: str
    created_by: UserId
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
            "email": self.email,
            "role": self.role,
            "created_by": str(self.created_by),
        })
        return base


@dataclass(frozen=True)
class UserDeactivated(DomainEvent):
    """Event raised when user account is deactivated."""
    user_id: UserId
    tenant_id: TenantId
    deactivated_by: UserId
    reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
            "deactivated_by": str(self.deactivated_by),
            "reason": self.reason,
        })
        return base


@dataclass(frozen=True)
class PasswordResetRequested(DomainEvent):
    """Event raised when password reset is initiated."""
    user_id: UserId
    tenant_id: TenantId
    email: str
    ip_address: Optional[str] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
            "email": self.email,
            "ip_address": self.ip_address,
        })
        return base


@dataclass(frozen=True)
class PasswordResetCompleted(DomainEvent):
    """Event raised when password is successfully reset."""
    user_id: UserId
    tenant_id: TenantId
    email: str
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
            "email": self.email,
        })
        return base


@dataclass(frozen=True)
class TokenRefreshed(DomainEvent):
    """Event raised when access token is refreshed."""
    user_id: UserId
    tenant_id: TenantId
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
        })
        return base