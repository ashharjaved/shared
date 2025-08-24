from __future__ import annotations

import logging
from uuid import UUID

from src.identity.domain.exceptions import AccountLockedError, InvalidCredentialsDomainError, TenantNotFoundError, UserInactiveError
from src.identity.domain.services.lockout_service import LockoutService
from src.config import get_settings
from src.identity.interfaces.repositories import TenantRepositoryPort, UserRepositoryPort
from src.shared.cache import get_cache
from src.shared.events import AuditEvent, emit_audit
from src.shared.exceptions import InvalidCredentialsError, NotFoundError, RateLimitedError
from src.shared.security import PasswordHasher, TokenProvider, Role
from src.identity.infrastructure.models import User as ORMUser

logger = logging.getLogger("app.auth")

class AuthenticationService:
    """
    Orchestrates login and password rotation.
    Depends on abstractions (DIP):
      - TenantRepositoryPort, UserRepositoryPort
      - PasswordHasher
      - TokenProvider
    """
    def __init__(
        self,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        hasher: PasswordHasher,
        tokens: TokenProvider,
    ):
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.hasher = hasher
        self.tokens = tokens
        self.lockouts = LockoutService()

    async def login(self, tenant_name: str, email: str, password: str) -> tuple[str, ORMUser]:
        tenant = await self.tenant_repo.get_by_name(tenant_name)
        if not tenant or not tenant.is_active:
            raise TenantNotFoundError("Tenant not found or inactive")

        user = await self.user_repo.get_by_email(email)
        if not user:
            emit_audit(AuditEvent(event_type="LoginFailure", tenant_id=tenant.id, user_id=None, metadata={"email": email}))
            raise InvalidCredentialsDomainError("Invalid credentials")
        if not user.is_active:
            emit_audit(AuditEvent(event_type="LoginFailure", tenant_id=tenant.id, user_id=user.id, metadata={"inactive": True}))
            raise UserInactiveError("User is inactive")

        if await self.lockouts.is_locked(tenant.id, user.id):
            raise AccountLockedError("Account temporarily locked due to too many failed attempts")

        if not self.hasher.verify(password, user.password_hash):
            attempts = int(user.failed_login_attempts or 0) + 1
            await self.user_repo.set_failed_attempts(user.id, attempts)
            emit_audit(AuditEvent(event_type="LoginFailure", tenant_id=tenant.id, user_id=user.id))
            if attempts >= self.lockouts.max_failed:
                await self.lockouts.lock(tenant.id, user.id)
            raise InvalidCredentialsDomainError("Invalid credentials")

        # success
        await self.user_repo.set_failed_attempts(user.id, 0)
        await self.lockouts.clear(tenant.id, user.id)
        await self.user_repo.set_last_login(user.id)
        token = self.tokens.encode(sub=user.id, tenant_id=user.tenant_id, role=Role(user.role))
        emit_audit(AuditEvent(event_type="LoginSuccess", tenant_id=tenant.id, user_id=user.id))
        return token, user

    async def change_password(self, current_user: ORMUser, old_pw: str, new_pw: str) -> None:
        if not self.hasher.verify(old_pw, current_user.password_hash):
            raise InvalidCredentialsDomainError("Invalid credentials")
        new_hash = self.hasher.hash(new_pw)
        await self.user_repo.change_password(current_user.id, new_hash)
        emit_audit(AuditEvent(event_type="PasswordChanged", tenant_id=current_user.tenant_id, user_id=current_user.id))