# src/identity/api/routes/tenants.py
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request

from src.shared.roles import Role
from src.identity.api.schemas import TenantCreate, TenantRead, TenantStatusUpdate
from src.identity.application.services.tenant_service import TenantService
from src.dependencies import get_current_user, get_tenant_repo, get_user_repo, require_role
from src.shared import security
from src.shared.exceptions import AuthorizationError, DomainConflictError, NotFoundError

router = APIRouter(prefix="/api/identity/tenants", tags=["identity:tenants"])


@router.post("", response_model=TenantRead, dependencies=[Depends(require_role(Role.RESELLER_ADMIN))])
async def create_tenant(
    payload: TenantCreate,
    request: Request,
    current_user = Depends(get_current_user),
    tenant_repo=Depends(get_tenant_repo),
    user_repo=Depends(get_user_repo),
) -> TenantRead:
    user_svc = __import__("src.identity.application.services.user_service", fromlist=["UserService"]).UserService(user_repo=user_repo, tenant_repo=tenant_repo)
    svc = TenantService(tenant_repo=tenant_repo, user_service=user_svc)
    try:
        tenant = svc.create_tenant(
            requester=current_user,
            name=payload.name,
            tenant_type=payload.tenant_type,
            parent_id=payload.parent_tenant_id,
            plan=payload.subscription_plan,
            seed_admin=None,  # optionally pass admin seed here
            correlation_id=request.headers.get("X-Correlation-ID"),
        )
        return TenantRead.model_validate(tenant)
    except (AuthorizationError, DomainConflictError) as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": str(e)})


@router.get("", response_model=list[TenantRead], dependencies=[Depends(require_role(Role.RESELLER_ADMIN))])
async def list_tenants(
    current_user = Depends(get_current_user),
    tenant_repo=Depends(get_tenant_repo),
) -> list[TenantRead]:
    # Prefer domain query service method if it exists; else fallback.
    if hasattr(tenant_repo, "list_accessible"):
        items = await tenant_repo.list_accessible(current_user) if callable(getattr(tenant_repo, "list_accessible")) else tenant_repo.list_accessible(current_user)
    elif hasattr(tenant_repo, "list_all"):
        items = await tenant_repo.list_all() if callable(getattr(tenant_repo, "list_all")) else tenant_repo.list_all()
    else:
        items = []
    return [TenantRead.model_validate(t) for t in items]


@router.put("/{tenant_id}", response_model=TenantRead, dependencies=[Depends(require_role(Role.RESELLER_ADMIN))])
async def update_tenant_status(
    tenant_id: str,
    payload: TenantStatusUpdate,
    request: Request,
    tenant_repo=Depends(get_tenant_repo),
    user_repo=Depends(get_user_repo),
) -> TenantRead:
    user_svc = __import__("src.identity.application.services.user_service", fromlist=["UserService"]).UserService(user_repo=user_repo, tenant_repo=tenant_repo)
    svc = TenantService(tenant_repo=tenant_repo, user_service=user_svc)
    try:
        updated = svc.update_tenant_status(tenant_id=tenant_id, is_active=payload.is_active, correlation_id=request.headers.get("X-Correlation-ID"))
        return TenantRead.model_validate(updated)
    except NotFoundError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": str(e)})
