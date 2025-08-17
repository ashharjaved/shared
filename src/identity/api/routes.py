from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from .schemas import (
    TenantCreate, TenantRead, TenantUpdate, TenantStatusUpdate,
    UserCreate, UserRead, TokenRequest, TokenResponse
)
from ..application.commands import (
    CreateTenant, CreateUser, AssignRole,
    UpdateTenant, UpdateTenantStatus
)
from ..application.queries import GetTenant, GetUser
from ..application.handlers import (
    handle_create_tenant, handle_get_tenant, handle_create_user, handle_get_user,
    handle_assign_role, verify_password, handle_update_tenant, handle_update_tenant_status
)
from ...shared.security import create_access_token, require_roles, get_principal, get_tenant_from_header
from ...shared.database import get_session
from ..infrastructure.repositories import TenantRepository, UserRepository
from ...identity.domain.entities import Principal

router = APIRouter(prefix="/api/v1/auth", tags=["Identity"])

# ---- Tenants (platform scoped) ----
@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def create_tenant(payload: TenantCreate, session: AsyncSession = Depends(get_session)):
    repo = TenantRepository(session)
    t = await handle_create_tenant(CreateTenant(**payload.dict()), repo)
    await session.commit()
    return TenantRead(
        id=t.id, name=t.name, tenant_type=t.tenant_type,
        subscription_status=t.subscription_status, is_active=t.is_active
    )

@router.get("/tenants", response_model=List[TenantRead], dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def list_tenants(session: AsyncSession = Depends(get_session)):
    repo = TenantRepository(session)
    rows = await repo.list(active_only=False)
    return [TenantRead(id=t.id, name=t.name, tenant_type=t.tenant_type,
                       subscription_status=t.subscription_status, is_active=t.is_active) for t in rows]

# NEW: update tenant fields
@router.patch("/tenants/{tenant_id}", response_model=TenantRead,
              dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def update_tenant(tenant_id: str, payload: TenantUpdate, session: AsyncSession = Depends(get_session)):
    repo = TenantRepository(session)
    t = await handle_update_tenant(UpdateTenant(tenant_id=tenant_id, **payload.dict()), repo)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await session.commit()
    return TenantRead(
        id=t.id, name=t.name, tenant_type=t.tenant_type,
        subscription_status=t.subscription_status, is_active=t.is_active
    )

# Existing status-by-path (kept for backward compat)
@router.post("/tenants/{tenant_id}/status/{status}", dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def set_tenant_status(tenant_id: str, status: str, session: AsyncSession = Depends(get_session)):
    repo = TenantRepository(session)
    if status not in {"activate", "deactivate"}:
        raise HTTPException(status_code=400, detail="status must be 'activate' or 'deactivate'")
    ok = await repo.set_status(tenant_id, is_active=(status == "activate"))
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"ok": True}

# NEW: status update via body (supports is_active and/or subscription_status)
@router.patch("/tenants/{tenant_id}/status",
              dependencies=[Depends(require_roles("SUPER_ADMIN"))])
async def patch_tenant_status(tenant_id: str, payload: TenantStatusUpdate, session: AsyncSession = Depends(get_session)):
    if payload.is_active is None and payload.subscription_status is None:
        raise HTTPException(status_code=400, detail="Provide is_active and/or subscription_status")
    repo = TenantRepository(session)
    t = await handle_update_tenant_status(UpdateTenantStatus(
        tenant_id=tenant_id,
        is_active=payload.is_active,
        subscription_status=payload.subscription_status
    ), repo)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await session.commit()
    return {
        "ok": True,
        "tenant": {
            "id": t.id,
            "is_active": t.is_active,
            "subscription_status": t.subscription_status
        }
    }

# ---- JWT (bootstrap allows X-Tenant-Id) ----
@router.post("/token", response_model=TokenResponse)
async def issue_token(
    payload: TokenRequest,
    session: AsyncSession = Depends(get_session),
    tenant_hint: Optional[str] = Depends(get_tenant_from_header),
):
    if not tenant_hint:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required for login")
    user_repo = UserRepository(session)
    user = await user_repo.by_email(tenant_hint, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, roles=user.roles, email=user.email)
    return TokenResponse(access_token=token, expires_in=60 * 60)

# ---- Users (tenant scoped; admin only) ----
@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    principal: Principal = Depends(require_roles("TENANT_ADMIN", "SUPER_ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    if principal.tenant_id != payload.tenant_id and "SUPER_ADMIN" not in principal.roles:
        raise HTTPException(status_code=403, detail="Cross-tenant user creation is not allowed")
    user_repo = UserRepository(session)
    u = await handle_create_user(CreateUser(**payload.dict()), user_repo)
    await session.commit()
    return UserRead(id=u.id, tenant_id=u.tenant_id, email=u.email, roles=u.roles, is_active=u.is_active, is_verified=u.is_verified)

@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: str,
    principal: Principal = Depends(require_roles("STAFF", "TENANT_ADMIN", "SUPER_ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    user_repo = UserRepository(session)
    u = await user_repo.by_id(principal.tenant_id, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if principal.user_id != u.id and not principal.has_any_role("TENANT_ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return UserRead(id=u.id, tenant_id=u.tenant_id, email=u.email, roles=u.roles, is_active=u.is_active, is_verified=u.is_verified)

@router.post("/users/{user_id}/roles", dependencies=[Depends(require_roles("TENANT_ADMIN", "SUPER_ADMIN"))])
async def assign_user_roles(
    user_id: str,
    roles: List[str],
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    user_repo = UserRepository(session)
    # Assign one by one to reuse existing handler; keep idempotency
    u = None
    for r in roles:
        u = await handle_assign_role(AssignRole(tenant_id=principal.tenant_id, user_id=user_id, role=r), user_repo)
    await session.commit()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "roles": u.roles}
