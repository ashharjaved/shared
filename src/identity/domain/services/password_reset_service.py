# src/identity/domain/services/password_reset_service.py

from datetime import datetime, timedelta
from typing import Optional
import secrets

from src.identity.domain.types import UserId
from src.identity.domain.value_objects.email import Email
from src.shared_.exceptions import ValidationError, NotFoundError


class PasswordResetToken:
    """
    Value object representing a password reset token.
    
    Encapsulates token generation, validation, and expiry logic.
    """
    
    TOKEN_LENGTH = 32
    EXPIRY_HOURS = 1
    
    def __init__(
        self,
        token: str,
        user_id: UserId,
        email: str,
        created_at: datetime,
        expires_at: datetime
    ):
        self.token = token
        self.user_id = user_id
        self.email = email
        self.created_at = created_at
        self.expires_at = expires_at
    
    @classmethod
    def create(cls, user_id: UserId, email: str) -> "PasswordResetToken":
        """
        Create a new password reset token.
        
        Args:
            user_id: User requesting reset
            email: User's email address
            
        Returns:
            New PasswordResetToken instance
        """
        token = secrets.token_urlsafe(cls.TOKEN_LENGTH)
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=cls.EXPIRY_HOURS)
        
        return cls(
            token=token,
            user_id=user_id,
            email=email,
            created_at=now,
            expires_at=expires_at
        )
    
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.utcnow() > self.expires_at
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate token is still usable.
        
        Returns:
            (is_valid, error_message)
        """
        if self.is_expired():
            return False, "Reset token has expired"
        
        if not self.token or len(self.token) < 16:
            return False, "Invalid token format"
        
        return True, None


class PasswordResetService:
    """
    Domain service for password reset operations.
    
    Handles token generation, validation, and password update logic.
    """
    
    def __init__(self, user_repository, password_hasher):
        """
        Initialize password reset service.
        
        Args:
            user_repository: UserRepository for data access
            password_hasher: PasswordHasher for secure hashing
        """
        self._user_repository = user_repository
        self._password_hasher = password_hasher
    
    async def initiate_reset(
        self, 
        email: str, 
        tenant_id: str
    ) -> Optional[PasswordResetToken]:
        """
        Initiate password reset for a user.
        
        Args:
            email: User's email address
            tenant_id: Tenant context
            
        Returns:
            PasswordResetToken if user found, None otherwise
            
        Note:
            Always returns success to prevent email enumeration attacks.
            Caller should send email only if token is not None.
        """
        try:
            email_vo = Email(email)
        except ValueError:
            # Invalid email format - return None silently
            return None
        
        user = await self._user_repository.find_by_email(
            str(email_vo),
            tenant_id
        )
        
        if not user or not user.is_active:
            # User not found or inactive - return None silently
            # to prevent email enumeration
            return None
        
        # Generate reset token
        return PasswordResetToken.create(user.id, str(email_vo))
    
    async def validate_reset_token(
        self,
        token: str,
        email: str
    ) -> tuple[bool, Optional[str], Optional[UserId]]:
        """
        Validate a reset token without consuming it.
        
        Args:
            token: Reset token string
            email: Email associated with token
            
        Returns:
            (is_valid, error_message, user_id)
        """
        # Note: In production, you'd load this from a token store
        # For now, this is a domain validation method
        
        if not token or len(token) < 16:
            return False, "Invalid token format", None
        
        if not email:
            return False, "Email required", None
        
        return True, None, None
    
    async def complete_reset(
        self,
        token: str,
        email: str,
        new_password: str,
        tenant_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Complete password reset with new password.
        
        Args:
            token: Valid reset token
            email: User's email
            new_password: New password (plain text)
            tenant_id: Tenant context
            
        Returns:
            (success, error_message)
        """
        try:
            email_vo = Email(email)
        except ValueError:
            return False, "Invalid email format"
        
        # Find user
        user = await self._user_repository.find_by_email(
            str(email_vo),
            tenant_id
        )
        
        if not user:
            return False, "Invalid reset request"
        
        # Validate password strength (domain rule)
        from src.identity.domain.services.auth_service import AuthService
        is_valid, error = AuthService(
            self._user_repository,
            self._password_hasher
        ).validate_password_strength(new_password)
        
        if not is_valid:
            return False, error
        
        # Hash new password
        hashed = self._password_hasher.hash(new_password)
        
        # Update user password
        from src.identity.domain.value_objects.password_hash import PasswordHash
        user.password_hash = PasswordHash(hashed)
        
        await self._user_repository.update(user)
        
        return True, None