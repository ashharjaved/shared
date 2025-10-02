# src/identity/domain/services/auth_service.py

from typing import Optional
from datetime import datetime

from src.identity.domain.types import TenantId, UserId
from src.identity.domain.entities.user import User
from src.identity.domain.value_objects.email import Email
from src.identity.domain.repositories.user_repository import UserRepository
from src.shared_.exceptions import AuthenticationError, AuthorizationError
from src.shared_.security.passwords.passlib_hasher import PasswordHasherPort


class AuthService:
    """
    Domain service for user authentication.
    
    Handles core authentication logic including credential validation,
    account status checks, and security event tracking.
    """
    
    def __init__(
        self, 
        user_repository: UserRepository,
        password_hasher: PasswordHasherPort
    ):
        self._user_repository = user_repository
        self._password_hasher = password_hasher
    
    async def authenticate_user(
        self, 
        email: str, 
        password: str, 
        tenant_id: TenantId
    ) -> User:
        """
        Authenticate user with email/password within tenant context.
        
        Args:
            email: User email address
            password: Plain text password
            tenant_id: Tenant context for authentication
            
        Returns:
            Authenticated User entity
            
        Raises:
            AuthenticationError: If credentials are invalid
            AuthorizationError: If account is inactive or locked
        """
        # Validate email format
        try:
            email_vo = Email(email)
        except ValueError as e:
            raise AuthenticationError("Invalid email format")
        
        # Find user by email within tenant
        user = await self._user_repository.find_by_email(
            str(email_vo), 
            tenant_id
        )
        
        if not user:
            # Use constant-time comparison to prevent timing attacks
            # Hash the password anyway to maintain consistent timing
            self._password_hasher.hash(password)
            raise AuthenticationError(
                "Invalid credentials",
                code="auth.invalid_credentials"
            )
        
        # Check account status
        if not user.is_active:
            raise AuthorizationError(
                "User account is inactive. Contact your administrator.",
                code="auth.account_inactive"
            )
        
        # Verify password using domain-injected hasher
        if not self._password_hasher.verify(password, user.password_hash):
            raise AuthenticationError(
                "Invalid credentials",
                code="auth.invalid_credentials"
            )
        
        # Update last login timestamp (domain operation)
        await self._user_repository.update_last_login(
            UserId(user.id), 
            datetime.utcnow()
        )
        
        return user
    
    async def verify_user_access(
        self, 
        user_id: UserId, 
        tenant_id: TenantId
    ) -> User:
        """
        Verify user exists and has access to tenant.
        
        Used for token validation and session checks.
        
        Args:
            user_id: User identifier
            tenant_id: Tenant context
            
        Returns:
            User entity if valid
            
        Raises:
            AuthenticationError: If user not found or no access
        """
        user = await self._user_repository.find_by_id(user_id)
        
        if not user:
            raise AuthenticationError(
                "User not found",
                code="auth.user_not_found"
            )
        
        if user.tenant_id != tenant_id:
            raise AuthorizationError(
                "User does not belong to this tenant",
                code="auth.tenant_mismatch"
            )
        
        if not user.is_active:
            raise AuthorizationError(
                "User account is inactive",
                code="auth.account_inactive"
            )
        
        return user
    
    def validate_password_strength(self, password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password meets security requirements.
        
        Domain rule: Passwords must be:
        - At least 8 characters
        - Contain uppercase and lowercase
        - Contain at least one number
        - Contain at least one special character
        
        Args:
            password: Plain text password
            
        Returns:
            (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"
        
        return True, None