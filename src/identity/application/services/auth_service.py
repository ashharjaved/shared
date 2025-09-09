"""
Authentication service implementation.
"""
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from identity.domain.value_objects.email import Email
from src.identity.domain.entities.user import User
from src.identity.domain.events.user_events import UserLoggedIn, UserLoginFailed
from src.identity.domain.repositories.users import UserRepository
from src.identity.domain.services.password_service import PasswordService
from src.identity.domain.services.token_service import TokenService
from src.identity.domain.types import TenantId, UserId
from src.identity.infrastructure.outbox.outbox_service import OutboxService
from src.shared.errors import DomainError, UnauthorizedError, ValidationError

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service handling user login, token generation, and security events."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
        token_service: TokenService,
        outbox_service: OutboxService,
    ):
        self.user_repository = user_repository
        self.password_service = password_service
        self.token_service = token_service
        self.outbox_service = outbox_service

    async def authenticate_user(
        self, email: Email, password: str, tenant_id: TenantId
    ) -> Tuple[User, str, str]:
        """
        Authenticate user with email and password.
        Returns user, access_token, and refresh_token.
        """
        # Get user by email
        user = await self.user_repository.get_by_email(email, tenant_id)
        if not user:
            # Log failed attempt for non-existent user
            await self._log_login_failed(str(email), "user_not_found", tenant_id)
            raise UnauthorizedError("Invalid credentials")

        # Check if user is active
        if not user.is_active:
            await self._log_login_failed(str(email), "user_inactive", tenant_id)
            raise UnauthorizedError("Account is deactivated")

        # Check if account is locked
        if user.is_locked:
            await self._log_login_failed(str(email), "account_locked", tenant_id)
            raise UnauthorizedError("Account is locked due to too many failed attempts")

        # Verify password
        if not self.password_service.verify_password(password, user.password_hash):
            # Increment failed attempts and check for lockout
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.is_locked = True
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            
            await self.user_repository.update(user)
            await self._log_login_failed(str(email), "invalid_password", tenant_id, user.id)
            raise UnauthorizedError("Invalid credentials")

        # Reset failed attempts on successful login
        if user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
            user.is_locked = False
            user.locked_until = None
            await self.user_repository.update(user)

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        await self.user_repository.update(user)

        # Generate tokens
        access_token, refresh_token = await self._generate_tokens(user)

        # Log successful login
        await self._log_login_success(user)

        return user, access_token, refresh_token

    async def refresh_tokens(self, refresh_token: str) -> Tuple[str, str]:
        """Refresh access token using valid refresh token."""
        # Validate refresh token
        payload = self.token_service.validate_token(refresh_token, is_refresh=True)
        if not payload:
            raise UnauthorizedError("Invalid refresh token")

        # Get user from token
        user_id = UUID(payload.get("sub"))
        tenant_id = UUID(payload.get("tenant_id"))
        
        user = await self.user_repository.get_by_id(UserId(user_id), TenantId(tenant_id))
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        # Generate new tokens
        access_token, new_refresh_token = await self._generate_tokens(user)

        return access_token, new_refresh_token

    async def logout(self, user_id: UserId, tenant_id: TenantId) -> None:
        """Invalidate user tokens (server-side token invalidation if needed)."""
        # In a stateless JWT setup, we might add tokens to a blacklist
        # or update user's token version to invalidate all previous tokens
        user = await self.user_repository.get_by_id(user_id, tenant_id)
        if user:
            user.token_version = (user.token_version or 0) + 1
            await self.user_repository.update(user)

    async def _generate_tokens(self, user: User) -> Tuple[str, str]:
        """Generate JWT tokens for user."""
        # Create token payload
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "tenant_id": str(user.tenant_id),
            "roles": [role.value for role in user.roles],
            "token_version": user.token_version or 0,
        }

        # Generate tokens
        access_token = self.token_service.generate_access_token(payload)
        refresh_token = self.token_service.generate_refresh_token(payload)

        return access_token, refresh_token

    async def _log_login_success(self, user: User) -> None:
        """Log successful login event to outbox."""
        event = UserLoggedIn.create(
            tenant_id=user.tenant_id,
            user_id=user.id,
            ip=None,  # Would come from request context
            user_agent=None,  # Would come from request context
        )
        await self.outbox_service.publish_event(event)

    async def _log_login_failed(
        self, email: str, reason: str, tenant_id: TenantId, user_id: Optional[UserId] = None
    ) -> None:
        """Log failed login event to outbox."""
        event = UserLoginFailed.create(
            tenant_id=tenant_id,
            email=email,
            reason=reason,
            attempts=None,  # Would be set based on current attempt count
        )
        await self.outbox_service.publish_event(event)