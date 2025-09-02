# src/identity/application/services/auth_service.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import uuid
from uuid import UUID
from src.config import settings
from src.identity.domain.entities.user import User
from src.identity.domain.repositories.user_repository import UserRepository
from src.shared.logging import log_security_event
from src.shared.exceptions import AuthenticationError, DomainError, AuthorizationError
from src.shared.security import verify_password, create_access_token, create_refresh_token

logger = logging.getLogger(__name__)

def _coerce_uuid(value: Any) -> uuid.UUID:
    """
    Normalize to a python uuid.UUID.
    Accepts asyncpg.pgproto.pgproto.UUID, uuid.UUID, or str.
    """
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))

def _role_str(role_obj: Any) -> str:
    """Return a stable string for role Enums or plain strings."""
    try:
        return role_obj.value  # Enum
    except AttributeError:
        return str(role_obj) if role_obj is not None else ""
class AuthService:
    """
    Application service for authentication operations.
    
    Handles user login, token generation, and security controls
    like failed login attempt tracking and account lockouts.
    """
    
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        tenant_id: UUID,
        correlation_id: str
    ) -> Dict[str, str]:
        """
        Authenticate user and return access/refresh tokens.
        
        Args:
            email: User email address
            password: Plain text password
            tenant_id: Tenant ID for user lookup
            correlation_id: Request correlation ID for logging
            
        Returns:
            Dictionary containing access_token and refresh_token
            
        Raises:
            AuthenticationError: If authentication fails
            AuthorizationError: If account is locked or inactive
        """
        # Find user by email and tenant
        user = await self._user_repository.find_by_email(email, tenant_id)
        
        if not user:
            await log_security_event(
                event="login_failed",
                tenant_id=str(tenant_id),
                email=email,
                reason="user_not_found",
                correlation_id=correlation_id
            )
            raise AuthenticationError("Invalid email or password")
        
        # Check if account is active
        if not user.is_active:
            await log_security_event(
                event="login_failed",
                tenant_id=str(tenant_id),
                user_id=str(user.id),
                email=email,
                reason="account_inactive",
                correlation_id=correlation_id
            )
            raise AuthorizationError("Account is inactive")
        
        # Check if account is verified
        if not user.is_verified:
            await log_security_event(
                event="login_failed",
                tenant_id=str(tenant_id),
                user_id=str(user.id),
                email=email,
                reason="account_not_verified",
                correlation_id=correlation_id
            )
            raise AuthorizationError("Account is not verified")
        
        # Check if account is locked due to failed attempts
        # if user.is_locked_at:
        #     await log_security_event(
        #         event="login_failed",
        #         tenant_id=str(tenant_id),
        #         user_id=str(user.id),
        #         email=email,
        #         reason="account_locked",
        #         correlation_id=correlation_id
        #     )
        #     raise AuthorizationError(
        #         f"Account is locked due to {user.failed_login_attempts} failed login attempts"
        #     )
        
        # Verify password
        if not verify_password(password, user.password_hash):
            # Increment failed login attempts
            failed_attempts = await self._user_repository.increment_failed_logins(user.id)
            
            await log_security_event(
                event="login_failed",
                tenant_id=str(tenant_id),
                user_id=str(user.id),
                email=email,
                reason="invalid_password",
                failed_attempts=failed_attempts,
                correlation_id=correlation_id
            )
            
            # Check if account should be locked
            if failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                await log_security_event(
                    event="account_locked",
                    tenant_id=str(tenant_id),
                    user_id=str(user.id),
                    email=email,
                    failed_attempts=failed_attempts,
                    correlation_id=correlation_id
                )
                raise AuthorizationError("Account has been locked due to too many failed attempts")
            
            raise AuthenticationError("Invalid email or password")
        
        # Successful authentication - reset failed attempts and update last login
        await self._user_repository.reset_failed_logins(user.id)
        await self._user_repository.update_last_login(user.id, datetime.utcnow())
        
        # Generate tokens
        tenant_uuid = _coerce_uuid(getattr(user, "tenant_id", None))
        role_str = _role_str(getattr(user, "role", None))
        access_token = create_access_token(
            sub=str(user.id),
            tenant_id=tenant_uuid,
            role=role_str,
            expires_delta=(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
        )
        
        refresh_token = create_refresh_token(
            sub=str(user.id),
            tenant_id=tenant_uuid,
            role=role_str,
            expires_delta = (timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
        )
        
        await log_security_event(
            event="login_success",
            tenant_id=str(tenant_id),
            user_id=str(user.id),
            email=email,
            role=user.role.value,
            correlation_id=correlation_id
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    async def refresh_access_token(
        self,
        refresh_token: str,
        correlation_id: str
    ) -> Dict[str, str]:
        """
        Refresh an access token using a valid refresh token.
        
        Args:
            refresh_token: The refresh token
            correlation_id: Request correlation ID for logging
            
        Returns:
            Dictionary containing new access_token and refresh_token
            
        Raises:
            AuthenticationError: If refresh token is invalid
            AuthorizationError: If user is no longer active
        """
        from src.shared.security import decode_token, extract_user_id_from_token
        
        try:
            # Decode and validate refresh token
            payload = decode_token(refresh_token)
            
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")
            
            user_id = extract_user_id_from_token(refresh_token)
            
        except Exception:
            raise AuthenticationError("Invalid refresh token")
        
        # Get current user
        user = await self._user_repository.find_by_id(user_id)
        
        if not user or not user.can_login:
            await log_security_event(
                event="token_refresh_failed",
                user_id=str(user_id) if user else None,
                tenant_id=str(payload["tenant_id"]) if "tenant_id" in payload else None,
                reason="user_inactive_or_not_found",
                correlation_id=correlation_id
            )
            raise AuthorizationError("User account is no longer active")
        
        # Generate new tokens
        access_token = create_access_token(
            sub=user.id,
            tenant_id=user.tenant_id,
            role=user.role.value,
            expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        new_refresh_token = create_refresh_token(
            sub=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
            expires_delta=(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
        )
        
        await log_security_event(
            event="token_refreshed",
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            correlation_id=correlation_id
        )
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    
    async def logout_user(
        self,
        user_id: UUID,
        correlation_id: str
    ) -> None:
        """
        Log out a user (placeholder for token blacklisting).
        
        Args:
            user_id: The user ID
            correlation_id: Request correlation ID for logging
        """
        user = await self._user_repository.find_by_id(user_id)
        
        if user:
            await log_security_event(
                event="logout",
                tenant_id=str(user.tenant_id),
                user_id=str(user.id),
                correlation_id=correlation_id
            )
        
        # Note: In a production system, you would typically:
        # 1. Add the token to a blacklist (Redis)
        # 2. Or implement token versioning
        # 3. Or use short-lived tokens with refresh rotation