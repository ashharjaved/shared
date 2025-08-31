# src/identity/application/services/tenant_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.shared.exceptions import AuthorizationError, DomainConflictError, NotFoundError
from src.shared.error_codes import ERROR_CODES
from src.shared.logging import log_event
from src.shared.roles import Role


@dataclass
class TenantService:
    tenant_repo: Any  # protocol: create, get_by_id, update_status, exists_by_name, etc.
    user_service: Any  # to seed initial admin if requested

    def _ensure_rls(self, tenant_id: Optional[str]) -> None:
        # For cross-tenant creation, SUPER/RESELLER can act without own-tenant RLS,
        # but we still require middleware to set context for write safety elsewhere.
        if tenant_id is None:
            # We don't strictly block SUPER_ADMIN here; RLS is enforced at DB policy level.
            pass

    def create_tenant(
        self,
        *,
        requester: Any,
        name: str,
        tenant_type: str,
        parent_id: Optional[str],
        plan: str,
        seed_admin: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Any:
        """
        RBAC:
          - SUPER_ADMIN can create RESELLER and CLIENT (anywhere).
          - RESELLER_ADMIN can create CLIENT under itself (parent_id must be reseller's tenant).
        """
        req_role = getattr(requester, "role", "")
        req_tenant = getattr(requester, "tenant_id", None)

        # Authorization logic
        if req_role == Role.SUPER_ADMIN:
            pass
        elif req_role == Role.RESELLER_ADMIN:
            # Can only create CLIENT under itself
            if tenant_type != "CLIENT" or parent_id != req_tenant:
                raise AuthorizationError(ERROR_CODES["forbidden"]["message"], code="forbidden", status_code=403)
        else:
            raise AuthorizationError(ERROR_CODES["forbidden"]["message"], code="forbidden", status_code=403)

        # Uniqueness by name (optional constraint)
        if hasattr(self.tenant_repo, "exists_by_name") and self.tenant_repo.exists_by_name(name):
            raise DomainConflictError("Tenant name already exists", code="conflict", status_code=409)

        tenant = self.tenant_repo.create(
            name=name,
            tenant_type=tenant_type,
            parent_id=parent_id,
            plan=plan,
            is_active=True,
        )
        log_event(
            "TenantCreated",
            tenant_id=getattr(tenant, "id", None),
            user_id=getattr(requester, "id", None),
            correlation_id=correlation_id,
            tenant_type=tenant_type,
            parent_id=parent_id,
            plan=plan,
        )

        # Optionally seed initial admin in the new tenant
        if seed_admin:
            admin_role = seed_admin.get("role", Role.TENANT_ADMIN if tenant_type == "CLIENT" else Role.RESELLER_ADMIN)
            admin_payload = {
                "tenant_id": getattr(tenant, "id", None),
                "email": seed_admin["email"],
                "password": seed_admin.get("password"),
                "full_name": seed_admin.get("full_name"),
                "role": admin_role,
                "metadata": seed_admin.get("metadata") or {},
            }
            # SUPER_ADMIN can create; RESELLER_ADMIN can create ADMIN in its client
            self.user_service.create_user(requester=requester, data=admin_payload, correlation_id=correlation_id)

        return tenant

    def update_tenant_status(self, *, tenant_id: str, is_active: bool, correlation_id: Optional[str] = None) -> Any:
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            data_ec = ERROR_CODES["tenant_not_found"]
            raise NotFoundError(data_ec["message"], code="tenant_not_found", status_code=data_ec["http"])

        updated = self.tenant_repo.update_status(tenant_id, is_active=is_active)
        log_event(
            "TenantStatusUpdated",
            tenant_id=tenant_id,
            user_id=None,
            correlation_id=correlation_id,
            is_active=is_active,
        )
        return updated
