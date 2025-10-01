# src/identity/application/services/user_service.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.domain.types import TenantId, UserId
from src.identity.domain.entities.user import User
from src.identity.domain.repositories.user_repository import UserRepository
from src.identity.domain.repositories.tenant_repository import TenantRepository
from src.identity.domain.services.rbac_policy import Role, RbacPolicy

from src.shared.database.uow import AsyncUoW
from src.shared.database.types import TenantContext
from src.shared.error_codes import ERROR_CODES
from src.shared.exceptions import (
    AuthorizationError,
    UnauthorizedError,
    DomainConflictError,
    NotFoundError,
)
from src.shared.structured_logging import log_event
from src.shared.security.passwords.ports import PasswordHasherPort


@dataclass(slots=True)
class UserService:
    """
    Application service for User lifecycle & admin actions.
    """
    uow_factory: Callable[..., AsyncUoW]
    user_repo_factory: Callable[[AsyncSession], UserRepository]
    tenant_repo_factory: Callable[[AsyncSession], TenantRepository]
    password_hasher: PasswordHasherPort

    # ---------- Helpers ----------
    def _hash(self, plain: Optional[str]) -> str:
        if not plain:
            ec = ERROR_CODES.get("invalid_password") or ERROR_CODES["bad_request"]
            raise DomainConflictError(ec["message"], code="invalid_password", status_code=ec["http"])
        return self.password_hasher.hash(plain)

    def _to_uuid(self, value: Union[str, UUID, TenantId, UserId]) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    def _to_user_id(self, value: Union[str, UUID, UserId]) -> UserId:
        return UserId(self._to_uuid(value))

    def _to_tenant_id(self, value: Union[str, UUID, TenantId]) -> TenantId:
        return TenantId(self._to_uuid(value))

    @staticmethod
    def _roles_of(actor: Any) -> list[Role]:
        raw = getattr(actor, "roles", []) or []
        roles: list[Role] = []
        for r in raw:
            roles.append(r if isinstance(r, Role) else Role(str(r)))
        # Also include single `role` field if present
        single = getattr(actor, "role", None)
        if single:
            roles.append(single if isinstance(single, Role) else Role(str(single)))
        # Deduplicate
        dedup = []
        seen = set()
        for r in roles:
            if r not in seen:
                seen.add(r)
                dedup.append(r)
        return dedup

    # ---------- Command ----------
    async def create_user(
        self,
        *,
        requester: Any,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> User:
        """
        RBAC:
          - SUPER_ADMIN: can create anywhere (impersonate target tenant for tx).
          - TENANT_ADMIN / RESELLER_ADMIN: can create only in their own tenant; optional role limits.

        Enforces unique (tenant_id, email). Applies RLS via UoW context override where needed.
        """
        req_tenant = getattr(requester, "tenant_id", None)
        req_roles = self._roles_of(requester)

        # Decide target tenant
        target_tenant_str = (data.get("tenant_id") or req_tenant)
        if target_tenant_str is None:
            ec = ERROR_CODES["forbidden"]
            raise AuthorizationError(ec["message"], code="forbidden", status_code=ec["http"])

        # RBAC checks (cross-tenant)
        if Role.SUPER_ADMIN in req_roles:
            # allowed: any tenant
            pass
        elif Role.RESELLER_ADMIN in req_roles or Role.TENANT_ADMIN in req_roles:
            if target_tenant_str != str(req_tenant):
                ec = ERROR_CODES["forbidden"]
                raise AuthorizationError(ec["message"], code="forbidden", status_code=ec["http"])
        else:
            ec = ERROR_CODES["forbidden"]
            raise AuthorizationError(ec["message"], code="forbidden", status_code=ec["http"])

        # Role normalization/limits for non-super
        requested_role_raw = data.get("role") or Role.TENANT_USER
        requested_role: Role = requested_role_raw if isinstance(requested_role_raw, Role) else Role(str(requested_role_raw))
        if Role.SUPER_ADMIN not in req_roles:
            # Example: only allow TENANT_USER creation by tenant admins; adjust as you like
            if Role.TENANT_ADMIN in req_roles and requested_role not in (Role.TENANT_USER,):
                ec = ERROR_CODES["role_change_not_allowed"]
                raise AuthorizationError(ec["message"], code="role_change_not_allowed", status_code=ec["http"])

        # Normalize inputs
        email = (data.get("email") or "").lower().strip()
        if not email:
            ec = ERROR_CODES.get("invalid_email") or ERROR_CODES["bad_request"]
            raise DomainConflictError(ec["message"], code="invalid_email", status_code=ec["http"])

        password_hash = self._hash(data.get("password"))

        # If SUPER_ADMIN → open UoW **impersonating the target tenant**
        ctx = TenantContext(
            tenant_id=str(target_tenant_str),
            user_id=str(getattr(requester, "id", "")),
            roles=[str(r) for r in req_roles],
        ) if (Role.SUPER_ADMIN in req_roles) else None

        async with self.uow_factory(require_tenant=True, context=ctx) as uow:
            session = uow.require_session()
            user_repo = self.user_repo_factory(session)
            tenant_repo = self.tenant_repo_factory(session)

            tenant_id = self._to_tenant_id(target_tenant_str)

            # Ensure tenant exists (under RLS of target tenant for super, or current for others)
            if not await tenant_repo.find_by_id(tenant_id):
                ec = ERROR_CODES["tenant_not_found"]
                raise NotFoundError(ec["message"], code="tenant_not_found", status_code=ec["http"])

            # Unique (tenant_id, email)
            if await user_repo.find_by_email(email=email, tenant_id=tenant_id):
                ec = ERROR_CODES["email_taken"]
                raise DomainConflictError(ec["message"], code="email_taken", status_code=ec["http"])

            new_user = User(
                id=uuid4(),
                tenant_id=tenant_id,
                email=email,
                password_hash=password_hash,
                role=requested_role,
                is_active=True,
                is_verified=True,
                failed_login_attempts=0,
                last_login=None,
                created_at=None,
                updated_at=None,
            )

            created = await user_repo.create(new_user)

            log_event(
                "UserCreated",
                tenant_id=str(tenant_id),
                user_id=str(getattr(created, "id", "")),
                correlation_id=correlation_id,
                created_by=str(getattr(requester, "id", "")),
                role=str(getattr(created, "role", "")),
            )
            return created

    async def change_user_role(
        self,
        *,
        requester: Any,
        target_user_id: Union[str, UUID, UserId],
        new_role: Union[str, Role],
        correlation_id: Optional[str] = None,
    ) -> User:
        req_role_raw = getattr(requester, "role", "")
        req_role: Role = req_role_raw if isinstance(req_role_raw, Role) else Role(str(req_role_raw))
        req_tenant = getattr(requester, "tenant_id", None)
        if req_tenant is None:
            ec = ERROR_CODES["forbidden"]
            raise UnauthorizedError(ec["message"], code="forbidden", status_code=ec["http"])

        async with self.uow_factory() as uow:
            session = uow.require_session()
            user_repo = self.user_repo_factory(session)

            uid = self._to_user_id(target_user_id)
            target = await user_repo.find_by_id(uid)

            if not target:
                ec = ERROR_CODES["user_not_found"]
                raise NotFoundError(ec["message"], code="user_not_found", status_code=ec["http"])

            if not RbacPolicy.can_manage_user(req_role, req_tenant, target.role, target.tenant_id):
                ec = ERROR_CODES["forbidden"]
                raise AuthorizationError(ec["message"], code="forbidden", status_code=ec["http"])

            new_role_enum: Role = new_role if isinstance(new_role, Role) else Role(str(new_role))
            if not RbacPolicy.has_min_role(req_role, new_role_enum):
                ec = ERROR_CODES["role_change_not_allowed"]
                raise AuthorizationError(ec["message"], code="role_change_not_allowed", status_code=ec["http"])

            updated = await user_repo.change_role(uid, new_role_enum)

            log_event(
                "UserRoleChanged",
                tenant_id=str(getattr(updated, "tenant_id", "")),
                user_id=str(getattr(updated, "id", "")),
                correlation_id=correlation_id,
                changed_by=str(getattr(requester, "id", "")),
                new_role=str(new_role_enum),
            )
            return updated

    async def deactivate_user(
        self,
        *,
        requester: Any,
        target_user_id: Union[str, UUID, UserId],
        correlation_id: Optional[str] = None,
    ) -> User:
        req_role_raw = getattr(requester, "role", "")
        req_role: Role = req_role_raw if isinstance(req_role_raw, Role) else Role(str(req_role_raw))
        req_tenant = getattr(requester, "tenant_id", None)
        if req_tenant is None:
            ec = ERROR_CODES["forbidden"]
            raise UnauthorizedError(ec["message"], code="forbidden", status_code=ec["http"])

        async with self.uow_factory() as uow:
            session = uow.require_session()
            user_repo = self.user_repo_factory(session)

            uid = self._to_user_id(target_user_id)
            target = await user_repo.find_by_id(uid)

            if not target:
                ec = ERROR_CODES["user_not_found"]
                raise NotFoundError(ec["message"], code="user_not_found", status_code=ec["http"])

            if not RbacPolicy.can_manage_user(req_role, req_tenant, target.role, target.tenant_id):
                ec = ERROR_CODES["forbidden"]
                raise AuthorizationError(ec["message"], code="forbidden", status_code=ec["http"])

            updated = await user_repo.deactivate(uid)

            log_event(
                "UserDeactivated",
                tenant_id=str(getattr(updated, "tenant_id", "")),
                user_id=str(getattr(updated, "id", "")),
                correlation_id=correlation_id,
                deactivated_by=str(getattr(requester, "id", "")),
            )
            return updated

    async def reactivate_user(
        self,
        *,
        requester: Any,
        target_user_id: Union[str, UUID, UserId],
        correlation_id: Optional[str] = None,
    ) -> User:
        req_role_raw = getattr(requester, "role", "")
        req_role: Role = req_role_raw if isinstance(req_role_raw, Role) else Role(str(req_role_raw))
        req_tenant = getattr(requester, "tenant_id", None)
        if req_tenant is None:
            ec = ERROR_CODES["forbidden"]
            raise UnauthorizedError(ec["message"], code="forbidden", status_code=ec["http"])

        async with self.uow_factory() as uow:
            session = uow.require_session()
            user_repo = self.user_repo_factory(session)
            uid = self._to_user_id(target_user_id)
            target = await user_repo.find_by_id(UserId(uid))
            if not target:
                ec = ERROR_CODES["user_not_found"]
                raise NotFoundError(ec["message"], code="user_not_found", status_code=ec["http"])

            if not RbacPolicy.can_manage_user(req_role, req_tenant, target.role, target.tenant_id):
                ec = ERROR_CODES["forbidden"]
                raise AuthorizationError(ec["message"], code="forbidden", status_code=ec["http"])

            updated = await user_repo.reactivate(uid)

            log_event(
                "UserReactivated",
                tenant_id=str(getattr(updated, "tenant_id", "")),
                user_id=str(getattr(updated, "id", "")),
                correlation_id=correlation_id,
                reactivated_by=str(getattr(requester, "id", "")),
            )
            return updated