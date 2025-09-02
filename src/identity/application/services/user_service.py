# src/identity/application/services/user_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from src.shared.roles import Role, can_manage_user, has_min_role
from src.shared.security import settings
from src.shared.exceptions import AuthorizationError, UnauthorizedError, DomainConflictError, NotFoundError, RlsNotSetError
from src.shared.error_codes import ERROR_CODES
from src.shared.logging import log_event
from src.shared import security

from src.identity.domain.entities.user import User

@dataclass
class UserService:
    user_repo: Any  # protocol: create, find_by_email, exists_by_email_in_tenant, get_by_id, change_role, deactivate, reactivate
    tenant_repo: Any  # protocol: get_by_id
    # Optional injectable hasher for testing
    password_hasher: Any = security.hash_password

    def _ensure_rls(self, tenant_id: Optional[str]) -> None:
        # RLS guard (GUC must be set by middleware). For now, enforce tenant present on requester.
        if not tenant_id:
            data = ERROR_CODES["rls_not_set"]
            raise RlsNotSetError(data["message"], code="rls_not_set", status_code=data["http"])

    async def create_user(self, *, requester: Any, data: Dict[str, Any], correlation_id: Optional[str] = None) -> Any:
        """
        RBAC:
        - SUPER_ADMIN/RESELLER_ADMIN: can operate broader (scoped policy can evolve).
        - TENANT_ADMIN: can create STAFF only within same tenant.
        Enforce unique (tenant_id, email).
        """
        req_role = getattr(requester, "role", "")
        req_tenant = getattr(requester, "tenant_id", None)
        target_tenant = data.get("tenant_id") or req_tenant

        self._ensure_rls(req_tenant or target_tenant)

        # Role + tenant authorization
        if req_role == Role.SUPER_ADMIN:
            pass  # always allowed
        elif req_role == Role.RESELLER_ADMIN:
            # For now, same-tenant scope; extend to reseller tree later.
            if target_tenant != req_tenant:
                raise UnauthorizedError(ERROR_CODES["forbidden"]["message"], code="forbidden", status_code=403)
        elif req_role == Role.TENANT_ADMIN:
            if target_tenant != req_tenant or data.get("role") not in (Role.STAFF, ):
                raise AuthorizationError(ERROR_CODES["forbidden"]["message"], code="forbidden", status_code=403)
        else:
            raise AuthorizationError(ERROR_CODES["forbidden"]["message"], code="forbidden", status_code=403)

        # Ensure tenant exists
        tenant = await self.tenant_repo.find_by_id(target_tenant)
        if not tenant:
            data_ec = ERROR_CODES["tenant_not_found"]
            raise NotFoundError(data_ec["message"], code="tenant_not_found", status_code=data_ec["http"])

        # Uniqueness in (tenant_id, email)
        email = data.get("email", "").lower().strip()
        existing = await self.user_repo.find_by_email(email=email, tenant_id=UUID(str(target_tenant)))
        if existing:
            data_ec = ERROR_CODES["email_taken"]
            raise DomainConflictError(data_ec["message"], code="email_taken", status_code=data_ec["http"])

        # Hash password if provided
        password = data.get("password")
        password_hash = self.password_hasher(password) if password else None

        # Build domain entity to satisfy repo.create(User)
        new_user = User(
            id=None,  # let DB default generate UUID
            tenant_id=UUID(str(target_tenant)),
            email=email,
            password_hash=password_hash,
            role=data.get("role") or Role.STAFF,
            is_active=True,
            is_verified=True,
            failed_login_attempts=0,
            last_login=None,
            created_at=None,
            updated_at=None,
        )

        user = await self.user_repo.create(new_user)
        log_event(
            "UserCreated",
            tenant_id=target_tenant,
            user_id=getattr(user, "id", None),
            correlation_id=correlation_id,
            created_by=getattr(requester, "id", None),
            role=getattr(user, "role", None),
        )
        return user

    def change_user_role(self, *, requester: Any, target_user_id: str, new_role: str,
                         correlation_id: Optional[str] = None) -> Any:
        req_role_raw = getattr(requester, "role", "")
        req_role: Role = req_role_raw if isinstance(req_role_raw, Role) else Role(str(req_role_raw))
        req_tenant = getattr(requester, "tenant_id", None)
        assert req_tenant is not None, "RLS guard should ensure tenant is set"
        self._ensure_rls(req_tenant)

        target = self.user_repo.find_by_id(target_user_id)
        if not target:
            data_ec = ERROR_CODES["user_not_found"]
            raise NotFoundError(data_ec["message"], code="user_not_found", status_code=data_ec["http"])

        if not can_manage_user(req_role, req_tenant, target.role, target.tenant_id):
            data_ec = ERROR_CODES["forbidden"]
            raise AuthorizationError(data_ec["message"], code="forbidden", status_code=data_ec["http"])

        # Basic safety: cannot escalate above yourself
        new_role_enum: Role = new_role if isinstance(new_role, Role) else Role(str(new_role))
        if not has_min_role(req_role, new_role_enum):
            data_ec = ERROR_CODES["role_change_not_allowed"]
            raise AuthorizationError(data_ec["message"], code="role_change_not_allowed", status_code=data_ec["http"])

        updated = self.user_repo.change_role(target_user_id, new_role)
        log_event(
            "UserRoleChanged",
            tenant_id=getattr(updated, "tenant_id", None),
            user_id=getattr(updated, "id", None),
            correlation_id=correlation_id,
            changed_by=getattr(requester, "id", None),
            new_role=new_role,
        )
        return updated

    def deactivate_user(self, *, requester: Any, target_user_id: str, correlation_id: Optional[str] = None) -> Any:
        req_role_raw = getattr(requester, "role", "")
        req_role: Role = req_role_raw if isinstance(req_role_raw, Role) else Role(str(req_role_raw))
        req_tenant = getattr(requester, "tenant_id", None)
        assert req_tenant is not None, "RLS guard should ensure tenant is set"
        self._ensure_rls(req_tenant)

        target = self.user_repo.find_by_id(target_user_id)
        if not target:
            data_ec = ERROR_CODES["user_not_found"]
            raise NotFoundError(data_ec["message"], code="user_not_found", status_code=data_ec["http"])

        if not can_manage_user(req_role, req_tenant, target.role, target.tenant_id):
            data_ec = ERROR_CODES["forbidden"]
            raise AuthorizationError(data_ec["message"], code="forbidden", status_code=data_ec["http"])

        updated = self.user_repo.deactivate(target_user_id)
        log_event(
            "UserDeactivated",
            tenant_id=getattr(updated, "tenant_id", None),
            user_id=getattr(updated, "id", None),
            correlation_id=correlation_id,
            deactivated_by=getattr(requester, "id", None),
        )
        return updated

    def reactivate_user(self, *, requester: Any, target_user_id: str, correlation_id: Optional[str] = None) -> Any:
        req_role_raw = getattr(requester, "role", "")
        req_role: Role = req_role_raw if isinstance(req_role_raw, Role) else Role(str(req_role_raw))
        

        req_tenant = getattr(requester, "tenant_id", None)
        assert req_tenant is not None, "RLS guard should ensure tenant is set"
        self._ensure_rls(req_tenant)

        target = self.user_repo.find_by_id(target_user_id)
        if not target:
            data_ec = ERROR_CODES["user_not_found"]
            raise NotFoundError(data_ec["message"], code="user_not_found", status_code=data_ec["http"])

        # Re-using same management rule
        if not can_manage_user(req_role, req_tenant, target.role, target.tenant_id):
            data_ec = ERROR_CODES["forbidden"]
            raise AuthorizationError(data_ec["message"], code="forbidden", status_code=data_ec["http"])

        updated = self.user_repo.reactivate(target_user_id)
        log_event(
            "UserReactivated",
            tenant_id=getattr(updated, "tenant_id", None),
            user_id=getattr(updated, "id", None),
            correlation_id=correlation_id,
            reactivated_by=getattr(requester, "id", None),
        )
        return updated
