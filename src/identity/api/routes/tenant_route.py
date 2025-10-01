# src/identity/api/routes/tenants.py
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request

from src.shared.database.database import get_session_factory
from src.identity.application.factories import make_tenant_service, make_user_service
from src.shared.security.passwords.factory import build_password_hasher
from src.identity.domain.services.rbac_policy import Role
from src.identity.api.schemas import TenantCreate, TenantRead, TenantStatusUpdate
from src.identity.application.services.tenant_service import TenantService
from src.shared.http.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/identity/tenants", tags=["Identity:Tenants"])


# --------- Dependency providers ------------------------------------------------
async def provide_tenant_service() -> "TenantService":
    """
    Assemble TenantService using composition factories.
    Keeps the service construction in one place for FastAPI DI.
    """
    session_factory = get_session_factory()
    password_hasher = build_password_hasher()

    user_svc = make_user_service(
        session_factory=session_factory,
        password_hasher=password_hasher,
    )
    tenant_svc = make_tenant_service(
        session_factory=session_factory,
        user_service=user_svc,
    )
    return tenant_svc


# --------- Routes --------------------------------------------------------------

@router.post(
    "",
    response_model=TenantRead,
    # Allow SUPER_ADMIN; RESELLER_ADMIN capability is enforced in the service RBAC
    # (so SUPER_ADMIN passes here; RESELLER_ADMIN is rejected here but can be allowed by
    # changing to require_role(Role.RESELLER_ADMIN) if you treat hierarchy as >=).
    dependencies=[Depends(require_role(Role.SUPER_ADMIN))],
)
async def create_tenant(
    payload: TenantCreate,
    request: Request,
    current_user=Depends(get_current_user),
    tenant_service=Depends(provide_tenant_service),
) -> TenantRead:
    """
    Create a tenant. RBAC & hierarchy are strictly enforced inside TenantService.
    Error contract: { code, message, details }.
    """
    correlation_id: Optional[str] = request.headers.get("X-Correlation-ID")
    try:
        tenant = await tenant_service.create_tenant(
            requester=current_user,
            name=payload.name,
            tenant_type=payload.tenant_type,
            parent_id=payload.parent_tenant_id,
            plan=None,
            seed_admin=None,  # can be None
            correlation_id=correlation_id,
        )
        return TenantRead.model_validate(tenant)
    except Exception as e:
        # Map domain/service exceptions to HTTP with your standard error contract
        status_code = getattr(e, "status_code", 400)
        code = getattr(e, "code", "invalid_request")
        message = str(e)
        details = getattr(e, "details", None)
        raise HTTPException(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details},
        )


@router.get(
    "/tenants",
    response_model=List[TenantRead],
    dependencies=[Depends(require_role(Role.SUPER_ADMIN))],
)
async def list_tenants(
    request: Request,
    current_user=Depends(get_current_user),
    tenant_service=Depends(provide_tenant_service),
) -> List[TenantRead]:
    """
    List tenants visible to the requester (RLS-enforced).
    Always goes through the UoW, which applies RLS GUCs for the transaction.
    """
    items = await tenant_service.list_all()
    return [TenantRead.model_validate(t) for t in items]


@router.put(
    "/{tenant_id}",
    response_model=TenantRead,
    dependencies=[Depends(require_role(Role.SUPER_ADMIN))],
)
async def update_tenant_status(
    tenant_id: str,
    payload: TenantStatusUpdate,
    request: Request,
    tenant_service=Depends(provide_tenant_service),
) -> TenantRead:
    """
    Activate/deactivate a tenant by id.
    Fixes missing 'await' bug from the previous version.
    """
    correlation_id: Optional[str] = request.headers.get("X-Correlation-ID")
    try:
        updated = await tenant_service.update_tenant_status(
            tenant_id=tenant_id,
            is_active=payload.is_active,
            correlation_id=correlation_id,
        )
        return TenantRead.model_validate(updated)
    except Exception as e:
        status_code = getattr(e, "status_code", 400)
        code = getattr(e, "code", "invalid_request")
        message = str(e)
        details = getattr(e, "details", None)
        raise HTTPException(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details},
        )
