# src/identity/application/services/tenant_service.py
# Source: :contentReference[oaicite:3]{index=3}
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database.uow import AsyncUoW
from src.shared.exceptions import AuthorizationError, DomainConflictError, NotFoundError
from src.shared.error_codes import ERROR_CODES
from src.shared.structured_logging import log_event
from src.identity.domain.services.rbac_policy import Role
from src.identity.domain.entities.tenant import Tenant, TenantType, SubscriptionPlan


# Repository factory type: given a live AsyncSession (managed by UoW), return a repo instance
TenantRepoFactory = Callable[[AsyncSession], Any]


@dataclass
class TenantService:
    """
    UoW-backed application service for Tenant lifecycle operations.
    Keeps the session open for the whole use-case and delegates persistence
    to repositories bound to that session.
    """
    uow_factory: Callable[[], AsyncUoW]
    tenant_repo_factory: TenantRepoFactory
    user_service: Any  # optional user seeding (create initial admin), must expose `create_user`

    # ------------ Helpers -----------------------------------------------------
    @staticmethod
    def _roles_of(principal: Any) -> set[str]:
        """
        Normalize principal roles to a set of strings.
        Supports both `role` (single) and `roles` (iterable).
        """
        out: set[str] = set()
        primary = getattr(principal, "role", None)
        many: Iterable[str] = getattr(principal, "roles", None) or []
        if primary:
            out.add(str(primary))
        for r in many:
            if r:
                out.add(str(r))
        return out

    # ------------ Queries -----------------------------------------------------
    async def list_all(self) -> list[Tenant]:
        """
        Return all tenants visible under RLS for the current context.
        Uses UoW so transaction is opened and RLS GUCs are applied.
        """
        async with self.uow_factory() as uow:
            session = uow.require_session()
            tenant_repo = self.tenant_repo_factory(session)
            # Assumes repo implements list_all() honoring RLS.
            return await tenant_repo.list_all()

    # ------------ Commands ----------------------------------------------------
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
        Create a tenant with strict RBAC and hierarchy rules.

        RBAC:
          - SUPER_ADMIN can create PLATFORM_OWNER / RESELLER / TENANT (anywhere, with valid parents where required).
          - RESELLER_ADMIN can create TENANT only under its own reseller tenant (parent auto-inferred).

        Notes:
          - Name uniqueness is enforced.
          - Enum strings are validated strictly.
          - Parent/child type compatibility enforced.
        """
        async with self.uow_factory() as uow:
            session = uow.require_session()
            tenant_repo = self.tenant_repo_factory(session)

            # ---- Authorization ------------------------------------------------
            req_roles = self._roles_of(requester)
            requester_tenant_id = getattr(requester, "tenant_id", None)

            if Role.SUPER_ADMIN in req_roles:
                pass  # full capability (subject to hierarchy checks below)
            elif Role.RESELLER_ADMIN in req_roles:
                # Only allow creating TENANT under their own reseller tenant
                if tenant_type.upper() != "TENANT":
                    raise AuthorizationError(
                        ERROR_CODES["forbidden"]["message"],
                        code="forbidden",
                        status_code=403,
                    )
            else:
                raise AuthorizationError(
                    ERROR_CODES["forbidden"]["message"],
                    code="forbidden",
                    status_code=403,
                )

            # ---- Uniqueness ---------------------------------------------------
            trimmed_name = name.strip()
            if await tenant_repo.find_by_name(trimmed_name):
                raise DomainConflictError(
                    "Tenant name already exists",
                    code="conflict",
                    status_code=409,
                )

            # ---- Enum validation ---------------------------------------------
            try:
                type_enum = TenantType(tenant_type)
            except ValueError:
                raise DomainConflictError(
                    f"Invalid tenant_type '{tenant_type}'",
                    code="validation_error",
                    status_code=422,
                )

            plan_enum: Optional[SubscriptionPlan] = None
            if plan is not None:
                try:
                    plan_enum = SubscriptionPlan(plan)
                except ValueError:
                    raise DomainConflictError(
                        f"Invalid subscription plan '{plan}'",
                        code="validation_error",
                        status_code=422,
                    )

            # ---- Hierarchy rules ---------------------------------------------
            effective_parent_id: Optional[UUID] = None
            tt = type_enum.name  # normalized

            if tt == "PLATFORM":
                # Root of tree
                effective_parent_id = None

            elif tt == "RESELLER":
                # Parent should be PLATFORM_OWNER when provided; otherwise try to resolve "Platform"
                if parent_id:
                    try:
                        pid = UUID(str(parent_id))
                    except ValueError:
                        raise DomainConflictError(
                            "parent_id must be a valid UUID",
                            code="validation_error",
                            status_code=422,
                        )
                    parent = await tenant_repo.find_by_id(pid)
                    if not parent:
                        raise NotFoundError(
                            "Parent tenant not found",
                            code="not_found",
                            status_code=404,
                        )
                    if parent.type is not TenantType.PLATFORM:
                        raise DomainConflictError(
                            "Reseller must have PLATFORM_OWNER as parent",
                            code="invalid_request",
                            status_code=422,
                        )
                    effective_parent_id = parent.id
                else:
                    # Convention-based fallback: locate the root platform row by name
                    platform = await tenant_repo.find_by_name("Platform")
                    if not platform:
                        raise NotFoundError(
                            "Root platform tenant not found; seed a PLATFORM first",
                            code="platform_not_found",
                            status_code=404,
                        )
                    effective_parent_id = platform.id

            elif tt == "TENANT":
                if Role.RESELLER_ADMIN in req_roles:
                    # Force parent as requester's reseller tenant
                    if not requester_tenant_id:
                        raise DomainConflictError(
                            "Requester has no tenant context",
                            code="invalid_request",
                            status_code=422,
                        )
                    reseller = await tenant_repo.find_by_id(UUID(str(requester_tenant_id)))
                    if not reseller:
                        raise NotFoundError(
                            "Requester reseller tenant not found",
                            code="not_found",
                            status_code=404,
                        )
                    if reseller.type is not TenantType.RESELLER:
                        raise DomainConflictError(
                            "Only RESELLER can be parent of TENANT",
                            code="invalid_request",
                            status_code=422,
                        )
                    effective_parent_id = reseller.id
                else:
                    # SUPER_ADMIN path (or other elevated roles if added later)
                    if not parent_id:
                        raise DomainConflictError(
                            "TENANT requires parent_tenant_id (a RESELLER or PLATFORM_OWNER)",
                            code="invalid_request",
                            status_code=422,
                        )
                    try:
                        pid = UUID(str(parent_id))
                    except ValueError:
                        raise DomainConflictError(
                            "parent_id must be a valid UUID",
                            code="validation_error",
                            status_code=422,
                        )
                    parent = await tenant_repo.find_by_id(pid)
                    if not parent:
                        raise NotFoundError(
                            "Parent tenant not found",
                            code="not_found",
                            status_code=404,
                        )
                    if parent.type not in {TenantType.RESELLER, TenantType.PLATFORM}:
                        raise DomainConflictError(
                            "TENANT parent must be RESELLER or PLATFORM_OWNER",
                            code="invalid_request",
                            status_code=422,
                        )
                    effective_parent_id = parent.id

            else:
                # Defensive; enumerations cover all supported types
                raise DomainConflictError(
                    f"Unknown tenant_type '{tenant_type}'",
                    code="invalid_request",
                    status_code=422,
                )

            # ---- Build & persist ---------------------------------------------
            now = datetime.now(timezone.utc)
            tenant_entity = Tenant(
                id=uuid4(),
                name=trimmed_name,
                type=type_enum,
                parent_tenant_id=effective_parent_id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )

            tenant = await tenant_repo.create(tenant_entity)

            log_event(
                "TenantCreated",
                tenant_id=str(getattr(tenant, "id", "")),
                user_id=str(getattr(requester, "id", "")),
                correlation_id=correlation_id,
                type=type_enum.value,
                parent_id=str(parent_id) if parent_id else None,
                plan=plan_enum.value if plan_enum else None,
            )

            # ---- Optional seed admin (post-commit semantics via same UoW) ----
            if seed_admin:
                admin_role = seed_admin.get(
                    "role",
                    Role.TENANT_ADMIN if tt == "TENANT" else Role.RESELLER_ADMIN,
                )
                admin_payload = {
                    "tenant_id": getattr(tenant, "id", None),
                    "password": seed_admin.get("password"),
                    "full_name": seed_admin.get("full_name"),
                    "role": admin_role,
                    "metadata": seed_admin.get("metadata") or {},
                }
                # Authorization is re-checked within user_service.
                await self.user_service.create_user(
                    requester=requester,
                    data=admin_payload,
                    correlation_id=correlation_id,
                )

            return tenant

    async def update_tenant_status(
        self,
        *,
        tenant_id: str,
        is_active: bool,
        correlation_id: Optional[str] = None,
    ) -> Any:
        """
        Activate/deactivate a tenant by id.
        """
        async with self.uow_factory() as uow:
            session = uow.require_session()
            tenant_repo = self.tenant_repo_factory(session)

            try:
                tid = UUID(str(tenant_id))
            except ValueError:
                raise DomainConflictError(
                    "tenant_id must be a valid UUID",
                    code="validation_error",
                    status_code=422,
                )

            tenant = await tenant_repo.find_by_id(tid)
            if not tenant:
                data_ec = ERROR_CODES["tenant_not_found"]
                raise NotFoundError(
                    data_ec["message"], code="tenant_not_found", status_code=data_ec["http"]
                )

            updated = await tenant_repo.update_status(tid, is_active=is_active)

            log_event(
                "TenantStatusUpdated",
                tenant_id=str(tenant_id),
                user_id=None,
                correlation_id=correlation_id,
                is_active=is_active,
            )
            return updated
