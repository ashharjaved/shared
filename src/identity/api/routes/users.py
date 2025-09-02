# src/identity/api/routes/users.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any

from src.shared.roles import Role
from src.identity.api.schemas import UserCreate, UserRead
from src.identity.application.services.user_service import UserService
from src.dependencies import get_current_user, get_user_repo, get_tenant_repo, require_role
from src.shared import security
from src.shared.exceptions import NotFoundError, AuthorizationError, DomainConflictError

router = APIRouter(prefix="/api/identity/users", tags=["identity:users"])


@router.get("/me", response_model=UserRead)
async def me(current_user = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("", response_model=UserRead, dependencies=[Depends(require_role(Role.TENANT_ADMIN))])
async def create_user(
    payload: UserCreate,
    request: Request,
    current_user = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    tenant_repo=Depends(get_tenant_repo),
) -> UserRead:
    svc = UserService(user_repo=user_repo, tenant_repo=tenant_repo)
    try:
        user =await svc.create_user(requester=current_user, data=payload.model_dump(), correlation_id=request.headers.get("X-Correlation-ID"))
        return UserRead.model_validate(user)
    except (DomainConflictError, AuthorizationError, NotFoundError) as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": str(e)})


@router.put("/{user_id}/role", response_model=UserRead, dependencies=[Depends(require_role(Role.TENANT_ADMIN))])
async def change_role(
    user_id: str,
    new_role: str,
    request: Request,
    current_user = Depends(get_current_user),
    user_repo=Depends(get_user_repo),
    tenant_repo=Depends(get_tenant_repo),
) -> UserRead:
    svc = UserService(user_repo=user_repo, tenant_repo=tenant_repo)
    try:
        user = svc.change_user_role(requester=current_user, target_user_id=user_id, new_role=new_role, correlation_id=request.headers.get("X-Correlation-ID"))
        return UserRead.model_validate(user)
    except (AuthorizationError, NotFoundError) as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": str(e)})
