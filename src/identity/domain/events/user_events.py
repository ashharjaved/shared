"""
User Domain Events
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from shared.domain.domain_event import DomainEvent


class UserCreatedEvent(DomainEvent):
    """Raised when a new user is created"""
    
    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        full_name: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.organization_id = organization_id
        self.email = email
        self.full_name = full_name


class UserLoggedInEvent(DomainEvent):
    """Raised when a user successfully logs in"""
    
    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.organization_id = organization_id
        self.email = email
        self.ip_address = ip_address
        self.user_agent = user_agent


class UserLockedEvent(DomainEvent):
    """Raised when a user account is locked due to failed attempts"""
    
    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        locked_until: datetime,
        reason: str = "excessive_failed_attempts",
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.organization_id = organization_id
        self.email = email
        self.locked_until = locked_until
        self.reason = reason


class UserUnlockedEvent(DomainEvent):
    """Raised when a user account is manually unlocked"""
    
    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        unlocked_by: Optional[UUID] = None,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.organization_id = organization_id
        self.email = email
        self.unlocked_by = unlocked_by


class EmailVerifiedEvent(DomainEvent):
    """Raised when a user's email is verified"""
    
    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.organization_id = organization_id
        self.email = email


class PhoneVerifiedEvent(DomainEvent):
    """Raised when a user's phone is verified"""
    
    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        phone: str,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.organization_id = organization_id
        self.phone = phone


class PasswordChangedEvent(DomainEvent):
    """Raised when a user's password is changed"""
    
    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        email: str,
        changed_by: Optional[UUID] = None,
        occurred_at: datetime | None = None,
    ) -> None:
        if occurred_at is not None:
            super().__init__(occurred_at=occurred_at)
        else:
            super().__init__()
        self.user_id = user_id
        self.organization_id = organization_id
        self.email = email
        self.changed_by = changed_by