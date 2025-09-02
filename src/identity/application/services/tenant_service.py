# src/identity/application/services/tenant_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from src.shared.exceptions import AuthorizationError, DomainConflictError, NotFoundError
from src.shared.error_codes import ERROR_CODES
from src.shared.logging import log_event
from src.shared.roles import Role
from src.identity.domain.entities.tenant import Tenant, TenantType, SubscriptionPlan

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

    async def create_tenant(
        self,
        *,
        requester: Any,
        name: str,
        tenant_type: str,
        parent_id: Optional[str],
        plan: Optional[str] = "BASIC",
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

        # Uniqueness by name using repository's async API
        existing = await self.tenant_repo.find_by_name(name)
        if existing:
            raise DomainConflictError("Tenant name already exists", code="conflict", status_code=409)
        
        # Build domain entity and persist via repo
        # --- Build domain entity (UUID, timestamps, enums, parent) ---
        # Map strings -> enums
        try:
            type_enum = TenantType(tenant_type)
        except ValueError:
            raise DomainConflictError(f"Invalid tenant_type '{tenant_type}'", code="validation_error", status_code=422)

        plan_enum = None
        if plan is not None:
            try:
                plan_enum = SubscriptionPlan(plan)
            except ValueError:
                raise DomainConflictError(f"Invalid subscription plan '{plan}'", code="validation_error", status_code=422)
        
        # ------------------------------------------------------------
        # Hierarchy resolution & validation (parent_tenant_id rules)
        # ------------------------------------------------------------
        effective_parent_id: Optional[UUID] = None
        tt = tenant_type.upper()

        if tt == "PLATFORM_OWNER":
            # Root of the tree
            effective_parent_id = None

        elif tt == "RESELLER":
            # Prefer explicit parent to be PLATFORM; otherwise auto-resolve the platform row
            if parent_id:
                # validate UUID
                try:
                    pid = UUID(str(parent_id))
                except ValueError:
                    raise DomainConflictError("parent_id must be a valid UUID", code="validation_error", status_code=422)
                maybe_parent = await self.tenant_repo.find_by_id(pid)
                if not maybe_parent:
                    raise NotFoundError("Parent tenant not found", code="not_found", status_code=404)
                if maybe_parent.type is not TenantType.PLATFORM_OWNER:
                    # Parent must be PLATFORM
                    raise DomainConflictError("Reseller must have PLATFORM_OWNER as parent", code="invalid_request", status_code=422)
                effective_parent_id = maybe_parent.id
            else:
                # Auto-resolve the single platform row (by convention name='Platform')
                platform = await self.tenant_repo.find_by_name("Platform")
                if not platform:
                    # No platform seeded yet
                    raise NotFoundError("Root platform tenant not found; seed a PLATFORM first", code="platform_not_found", status_code=404)
                effective_parent_id = platform.id

        elif tt == "CLIENT":
            # If requester is RESELLER_ADMIN, default parent to the reseller they belong to
            req_roles = {*(getattr(requester, "roles", []) or []), getattr(requester, "role", None)}
            req_roles = {r for r in req_roles if r}
            if "RESELLER_ADMIN" in req_roles:
                # Attach under the requester's reseller tenant
                requester_tenant_id = getattr(requester, "tenant_id", None)
                if not requester_tenant_id:
                    raise DomainConflictError("Requester has no tenant context", code="invalid_request", status_code=422)
                reseller = await self.tenant_repo.find_by_id(UUID(str(requester_tenant_id)))
                if not reseller:
                    raise NotFoundError("Requester reseller tenant not found", code="not_found", status_code=404)
                if reseller.type is not TenantType.RESELLER:
                    raise DomainConflictError("Only RESELLER can be parent of CLIENT", code="invalid_request", status_code=422)
                effective_parent_id = reseller.id
            else:
                # SUPER_ADMIN path (or others if allowed): require/accept a valid parent
                if not parent_id:
                    raise DomainConflictError("CLIENT requires parent_tenant_id (a RESELLER or PLATFORM)", code="invalid_request", status_code=422)
                try:
                    pid = UUID(str(parent_id))
                except ValueError:
                    raise DomainConflictError("parent_id must be a valid UUID", code="validation_error", status_code=422)
                parent = await self.tenant_repo.find_by_id(pid)
                if not parent:
                    raise NotFoundError("Parent tenant not found", code="not_found", status_code=404)
                if parent.type not in {TenantType.RESELLER, TenantType.PLATFORM_OWNER}:
                    raise DomainConflictError("CLIENT parent must be RESELLER or PLATFORM", code="invalid_request", status_code=422)
                effective_parent_id = parent.id

        else:
            raise DomainConflictError(f"Unknown tenant_type '{tenant_type}'", code="invalid_request", status_code=422)


        now = datetime.now(timezone.utc)
        tenant_entity = Tenant(
            id=uuid4(),
            name=name.strip(),
            type=type_enum,
            parent_tenant_id=effective_parent_id,
            plan=plan_enum,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        # --- Persist via repo (await!) ---
        tenant = await self.tenant_repo.create(tenant_entity)
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
            await self.user_service.create_user(requester=requester, data=admin_payload, correlation_id=correlation_id)

        return tenant

    def update_tenant_status(self, *, tenant_id: str, is_active: bool, correlation_id: Optional[str] = None) -> Any:
        tenant = self.tenant_repo.find_by_id(tenant_id)
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
