"""
User Entity - Authentication & Authorization
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from shared.domain.base_aggregate_root import BaseAggregateRoot
from src.identity.domain.value_objects.email import Email
from src.identity.domain.value_objects.phone import Phone
from src.identity.domain.value_objects.password_hash import PasswordHash
from src.identity.domain.events.user_events import (
    UserCreatedEvent,
    UserLoggedInEvent,
    UserLockedEvent,
    UserUnlockedEvent,
    EmailVerifiedEvent,
    PhoneVerifiedEvent,
    PasswordChangedEvent,
)
from src.identity.domain.exception import (
    AccountLockedException,
    InvalidCredentialsException,
    EmailNotVerifiedException,
)


class User(BaseAggregateRoot):
    """
    User aggregate root for authentication and authorization.
    
    Handles login attempts, account locking, and email/phone verification.
    Users belong to an organization and can have multiple roles.
    
    Attributes:
        organization_id: Parent organization UUID
        email: User email address (unique)
        phone: Optional phone number
        password_hash: Argon2id hashed password
        full_name: Display name
        is_active: Account status
        email_verified: Email verification status
        phone_verified: Phone verification status
        last_login_at: Last successful login timestamp
        failed_login_attempts: Count of consecutive failed logins
        locked_until: Account lock expiry timestamp
    """
    
    MAX_FAILED_ATTEMPTS = 5
    LOCK_DURATION_MINUTES = 30
    
    def __init__(
        self,
        id: UUID,
        organization_id: UUID,
        email: Email,
        password_hash: PasswordHash,
        full_name: str,
        phone: Optional[Phone] = None,
        is_active: bool = True,
        email_verified: bool = False,
        phone_verified: bool = False,
        last_login_at: Optional[datetime] = None,
        failed_login_attempts: int = 0,
        locked_until: Optional[datetime] = None,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(id, created_at=created_at, updated_at=updated_at)
        self._organization_id = organization_id
        self._email = email
        self._phone = phone
        self._password_hash = password_hash
        self._full_name = full_name
        self._is_active = is_active
        self._email_verified = email_verified
        self._phone_verified = phone_verified
        self._last_login_at = last_login_at
        self._failed_login_attempts = failed_login_attempts
        self._locked_until = locked_until
        self._metadata = metadata or {}
    
    @staticmethod
    def create(
        id: UUID,
        organization_id: UUID,
        email: Email,
        password_hash: PasswordHash,
        full_name: str,
        phone: Optional[Phone] = None,
    ) -> User:
        """
        Factory method to create a new user.
        
        Args:
            id: User UUID
            organization_id: Organization UUID
            email: Email address
            password_hash: Hashed password
            full_name: User's full name
            phone: Optional phone number
            
        Returns:
            New User instance with CreatedEvent raised
        """
        user = User(
            id=id,
            organization_id=organization_id,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            phone=phone,
            is_active=True,
            email_verified=False,
            phone_verified=False,
        )
        
        user.raise_event(
            UserCreatedEvent(
                user_id=id,
                organization_id=organization_id,
                email=str(email),
                full_name=full_name,
            )
        )
        
        return user
    
    def is_locked(self) -> bool:
        """Check if account is currently locked"""
        if self._locked_until is None:
            return False
        return datetime.utcnow() < self._locked_until
    
    def verify_password(
        self,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Verify password and handle failed attempts.
        
        Args:
            password: Plain text password to verify
            ip_address: Client IP address
            user_agent: Client user agent
            
        Raises:
            AccountLockedException: If account is locked
            InvalidCredentialsException: If password is incorrect
        """
        if not self._is_active:
            raise InvalidCredentialsException()
        
        if self.is_locked():
            raise AccountLockedException(unlock_at=self._locked_until)
        
        if not self._password_hash.verify(password):
            self._handle_failed_login()
            raise InvalidCredentialsException()
        
        # Success - reset failed attempts and update login time
        self._failed_login_attempts = 0
        self._locked_until = None
        self._last_login_at = datetime.utcnow()
        self._touch()
        
        # Raise login event
        self.raise_event(
            UserLoggedInEvent(
                user_id=self.id,
                organization_id=self._organization_id,
                email=str(self._email),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
    
    def _handle_failed_login(self) -> None:
        """Handle failed login attempt and lock if threshold exceeded"""
        self._failed_login_attempts += 1
        
        if self._failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            self._locked_until = datetime.utcnow() + timedelta(
                minutes=self.LOCK_DURATION_MINUTES
            )
            
            # Raise lock event
            self.raise_event(
                UserLockedEvent(
                    user_id=self.id,
                    organization_id=self._organization_id,
                    email=str(self._email),
                    locked_until=self._locked_until,
                )
            )
        
        self._touch()
    
    def unlock_account(self, unlocked_by: Optional[UUID] = None) -> None:
        """Manually unlock account (admin action)"""
        if not self.is_locked():
            return
        
        self._failed_login_attempts = 0
        self._locked_until = None
        self._touch()
        
        self.raise_event(
            UserUnlockedEvent(
                user_id=self.id,
                organization_id=self._organization_id,
                email=str(self._email),
                unlocked_by=unlocked_by,
            )
        )
    
    def verify_email(self) -> None:
        """Mark email as verified"""
        if self._email_verified:
            return
        
        self._email_verified = True
        self._touch()
        
        self.raise_event(
            EmailVerifiedEvent(
                user_id=self.id,
                organization_id=self._organization_id,
                email=str(self._email),
            )
        )
    
    def verify_phone(self) -> None:
        """Mark phone as verified"""
        if self._phone_verified or self._phone is None:
            return
        
        self._phone_verified = True
        self._touch()
        
        self.raise_event(
            PhoneVerifiedEvent(
                user_id=self.id,
                organization_id=self._organization_id,
                phone=str(self._phone),
            )
        )
    
    def update_password(
        self,
        new_password_hash: PasswordHash,
        changed_by: Optional[UUID] = None,
    ) -> None:
        """Update user password"""
        self._password_hash = new_password_hash
        self._failed_login_attempts = 0
        self._locked_until = None
        self._touch()
        
        self.raise_event(
            PasswordChangedEvent(
                user_id=self.id,
                organization_id=self._organization_id,
                email=str(self._email),
                changed_by=changed_by,
            )
        )
    
    def deactivate(self) -> None:
        """Deactivate user account"""
        self._is_active = False
        self._touch()
    
    def activate(self) -> None:
        """Activate user account"""
        self._is_active = True
        self._touch()
    
    def require_email_verified(self) -> None:
        """
        Require email verification for certain operations.
        
        Raises:
            EmailNotVerifiedException: If email not verified
        """
        if not self._email_verified:
            raise EmailNotVerifiedException()
    
    # Properties
    @property
    def organization_id(self) -> UUID:
        return self._organization_id
    
    @property
    def email(self) -> Email:
        return self._email
    
    @property
    def phone(self) -> Optional[Phone]:
        return self._phone
    
    @property
    def password_hash(self) -> PasswordHash:
        return self._password_hash
    
    @property
    def full_name(self) -> str:
        return self._full_name
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @property
    def email_verified(self) -> bool:
        return self._email_verified
    
    @property
    def phone_verified(self) -> bool:
        return self._phone_verified
    
    @property
    def last_login_at(self) -> Optional[datetime]:
        return self._last_login_at
    
    @property
    def metadata(self) -> dict:
        return self._metadata