# src/identity/application/services/auth_application_service.py

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
import uuid

from identity.domain.types import TenantId, UserId
from messaging.domain.interfaces.event_bus import EventBus
from src.identity.domain.services.auth_service import AuthService
from src.identity.domain.services.token_policy import TokenPolicy
from src.identity.domain.events.auth_events import (
    UserLoggedIn,
    UserLoginFailed,
    UserLoggedOut,
    TokenRefreshed,
)
from src.identity.application.services.login_rate_limiter import LoginRateLimiter
#from src.shared.events.event_bus import EventBus
from src.shared.exceptions import AuthenticationError, AuthorizationError

import structlog

logger = structlog.get_logger()

def _coerce_uuid(value: Any) -> uuid.UUID:
    """Normalize to python uuid.UUID (accepts asyncpg UUID, uuid.UUID or str)."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _role_str(role_obj: Any) -> str:
    """Return a stable string for role Enums or plain strings."""
    try:
        return role_obj.value  # Enum-like
    except AttributeError:
        return str(role_obj) if role_obj is not None else ""


class AuthenticationService:
    """
    Authentication application service.

    - Uses Unit of Work for transactional boundaries.
    - Repositories are instantiated per-UoW/session (no global sessions).
    - Repositories DO NOT commit; UoW coordinates commit/rollback.
    """

    def __init__(
        self,
        auth_service: AuthService,
        event_bus: EventBus,
        rate_limiter: LoginRateLimiter,
        token_service,  # Infrastructure token generation service
    ):
        self._auth_service = auth_service
        self._event_bus = event_bus
        self._rate_limiter = rate_limiter
        self._token_service = token_service
        
    async def authenticate_user(
        self,
        *,
        email: str,
        password: str,
        tenant_id: TenantId,
        correlation_id: str,
    ) -> Dict[str, str]:
        """
        Authenticate user and return access/refresh tokens.

        Raises:
            AuthenticationError | AuthorizationError on failure.
        """
        async with self._uow_factory(require_tenant=False) as uow:
            session = uow.session  
            if session is None:
                raise RuntimeError("UoW session is not initialized")
            await set_rls_gucs(session, tenant_id=str(tenant_id), user_id=None, roles_csv=None)
            user_repo: UserRepository = UserRepositoryImpl(session)  # per-UoW repo

            user = await user_repo.find_by_email(email, tenant_id)
            if not user:
                # NOTE: logging is sync; DO NOT 'await' it.
                await log_security_event(
                    event_type="login_failed",
                    tenant_id=str(tenant_id),
                    email=email,
                    reason="user_not_found",
                    correlation_id=correlation_id,
                )
                # No DB mutation yet -> no need to commit
                raise AuthenticationError("Invalid email or password")

            if not user.is_active:
                await log_security_event(
                    event_type="login_failed",
                    tenant_id=str(tenant_id),
                    user_id=str(user.id),
                    email=email,
                    reason="account_inactive",
                    correlation_id=correlation_id,
                )
                # No DB mutation -> no need to commit
                raise AuthorizationError("Account is inactive")

            if not user.is_verified:
                await log_security_event(
                    event_type="login_failed",
                    tenant_id=str(tenant_id),
                    user_id=str(user.id),
                    email=email,
                    reason="account_not_verified",
                    correlation_id=correlation_id,
                )
                # No DB mutation -> no need to commit
                raise AuthorizationError("Account is not verified")

            # Verify password
            if not self._hasher.verify(password, user.password_hash):
                # Increment failed attempts (DB mutation) — persist even if we raise.
                failed_attempts = await user_repo.increment_failed_logins(UserId(user.id))
                # Persist the increment before raising to survive UoW rollback-on-exception.
                await uow.commit()

                await log_security_event(
                    event_type="login_failed",
                    tenant_id=str(tenant_id),
                    user_id=str(user.id),
                    email=email,
                    reason="invalid_password",
                    failed_attempts=failed_attempts,
                    correlation_id=correlation_id,
                )

                if failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                    await log_security_event(
                        event_type="account_locked",
                        tenant_id=str(tenant_id),
                        user_id=str(user.id),
                        email=email,
                        failed_attempts=failed_attempts,
                        correlation_id=correlation_id,
                    )
                    raise AuthorizationError(
                        "Account has been locked due to too many failed attempts"
                    )

                raise AuthenticationError("Invalid email or password")

            # Success: reset counters & update last_login (mutations committed together)
            await user_repo.reset_failed_logins(UserId(user.id))
            await user_repo.update_last_login(UserId(user.id), datetime.now(timezone.utc))

            tenant_uuid = _coerce_uuid(getattr(user, "tenant_id", None))
            role_str = _role_str(getattr(user, "role", None))

            access_token = self._tokens.create_access(
                sub=str(user.id),
                tenant_id=tenant_uuid,
                role=role_str,
            )
            refresh_token = self._tokens.create_refresh(
                sub=str(user.id),
                tenant_id=tenant_uuid,
                role=role_str,
            )

            # Commit all successful mutations
            await uow.commit()

        # Log success outside the UoW (non-DB side-effect)
        await log_security_event(
            event_type="login_success",
            tenant_id=str(tenant_id),
            user_id=str(user.id),
            email=email,
            role=role_str,
            correlation_id=correlation_id,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def login(
        self,
        email: str,
        password: str,
        tenant_id: str,
        correlation_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """
        Authenticate user and issue tokens.
        
        Args:
            email: User email
            password: Plain text password
            tenant_id: Tenant context
            ip_address: Request IP (optional, for audit)
            user_agent: Request user agent (optional, for audit)
            
        Returns:
            {
                "access_token": str,
                "refresh_token": str,
                "expires_in": int,
                "user": UserDTO
            }
            
        Raises:
            AuthenticationError: If credentials invalid
            AuthorizationError: If account locked/inactive
        """
        # Check rate limiting
        is_allowed, error_msg = await self._rate_limiter.check_and_increment(email)
        if not is_allowed:
            # Emit failed login event
            await self._emit_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason="account_locked",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthorizationError(message=str(error_msg))
        
        try:
            # Authenticate user (domain logic)
            user = await self._auth_service.authenticate_user(
                email=email,
                password=password,
                tenant_id=TenantId(UUID(tenant_id))
            )
            
            # Clear rate limit counter on success
            await self._rate_limiter.record_success(email)
            
            # Generate tokens
            access_token = self._token_service.create_access(
                sub=str(user.id),
                tenant_id=str(user.tenant_id),
                role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            )
            
            refresh_token = self._token_service.create_refresh(
                sub=str(user.id),
                tenant_id=str(user.tenant_id),
                role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            )
            
            # Emit successful login event
            await self._emit_login_success(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            
            logger.info(
                "User logged in successfully",
                user_id=str(user.id),
                tenant_id=str(user.tenant_id),
                email=email,
            )
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": int(TokenPolicy.ACCESS_TOKEN_LIFETIME.total_seconds()),
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                    "tenant_id": str(user.tenant_id),
                },
            }
        
        except (AuthenticationError, AuthorizationError) as e:
            # Record failure for rate limiting
            await self._rate_limiter.record_failure(email)
            
            # Emit failed login event
            reason = "invalid_password" if isinstance(e, AuthenticationError) else "user_inactive"
            await self._emit_login_failed(
                email=email,
                tenant_id=tenant_id,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            
            logger.warning(
                "Login failed",
                email=email,
                tenant_id=tenant_id,
                reason=reason,
            )
            
            raise

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        tenant_id: TenantId,
        correlation_id: str,
    ) -> Dict[str, str]:
        """
        Deprecated alias kept for backward compatibility.
        """
        return await self.login(
            email=email,
            password=password,
            tenant_id=str(tenant_id),
            correlation_id=correlation_id,
        )

    async def logout_user(self, *, user_id: UUID, correlation_id: str) -> None:
        """
        Placeholder for token blacklisting / versioning.
        """
        async with self._uow_factory() as uow:
            session = uow.session  
            if session is None:
                raise RuntimeError("UoW session is not initialized")
            user_repo: UserRepository = UserRepositoryImpl(session)
            user = await user_repo.find_by_id(UserId(user_id))
            # No DB mutation by default
            await uow.commit()
        # Emit logout event
        event = UserLoggedOut(
            timestamp=datetime.utcnow(),
            event_id=str(uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
        )
        await self._event_bus.publish(event)
        
        logger.info("User logged out", user_id=user_id, tenant_id=tenant_id)
        if user:
            await log_security_event(
                event_type="logout",
                tenant_id=str(user.tenant_id),
                user_id=str(user.id),
                email=user.email,
                role=_role_str(user.role),
                correlation_id=correlation_id,
            )

    async def refresh_token(self, refresh_token: str) -> dict:
        """
        Issue new access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            {
                "access_token": str,
                "refresh_token": str,  # Optionally rotated
                "expires_in": int
            }
            
        Raises:
            AuthenticationError: If refresh token invalid/expired
        """
        try:
            # Decode and validate refresh token
            claims = self._token_service.decode(refresh_token)
            
            # Validate token type
            is_valid, error = TokenPolicy.validate_refresh_token_claims(claims)
            if not is_valid:
                raise AuthenticationError(message= str(error))
            
            # Extract user context
            user_id, tenant_id, role = TokenPolicy.extract_user_context(claims)
            
            # Verify user still has access
            user = await self._auth_service.verify_user_access(UserId(UUID(user_id)), TenantId(UUID(tenant_id)))
            
            # Issue new access token
            access_token = self._token_service.create_access(
                sub=user_id,
                tenant_id=tenant_id,
                role=role,
            )
            
            # Optional: Rotate refresh token
            new_refresh_token = self._token_service.create_refresh(
                sub=user_id,
                tenant_id=tenant_id,
                role=role,
            )
            
            # Emit token refreshed event
            event = TokenRefreshed(
                timestamp=datetime.utcnow(),
                event_id=str(uuid4()),
                user_id=UserId(UUID(user_id)),
                tenant_id=TenantId(UUID(tenant_id)))
            await self._event_bus.publish(event)
            
            logger.info(
                "Token refreshed",
                user_id=user_id,
                tenant_id=tenant_id,
            )
            
            return {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "expires_in": int(TokenPolicy.ACCESS_TOKEN_LIFETIME.total_seconds()),
            }
        
        except Exception as e:
            logger.warning("Token refresh failed", error=str(e))
            raise AuthenticationError("Invalid or expired refresh token")


    async def _emit_login_success(
        self,
        user,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Emit successful login domain event."""
        event = UserLoggedIn(
            timestamp=datetime.utcnow(),
            event_id=str(uuid4()),
            user_id=UserId(UUID(user.id)),
            tenant_id=TenantId(UUID(user.tenant_id)),
            email=user.email.value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._event_bus.publish(event)
        
    async def _emit_login_failed(
        self,
        email: str,
        tenant_id: str,
        reason: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Emit failed login domain event."""
        event = UserLoginFailed(
            timestamp=datetime.utcnow(),
            event_id=str(uuid4()),
            email=email,
            tenant_id=TenantId(UUID(tenant_id)),
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._event_bus.publish(event)