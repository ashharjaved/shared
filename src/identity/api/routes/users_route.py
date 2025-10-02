# src/identity/api/routes/users.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any

from src.shared_.security.passwords.factory import build_password_hasher
from src.identity.domain.services.rbac_policy import Role
from src.identity.api.schemas import UserCreate, UserRead
from src.identity.application.services.user_service import UserService
from src.identity.application.factories import make_user_service  # UoW-aware
from src.shared_.http.dependencies import get_current_user, require_role
from src.shared_.exceptions import NotFoundError, AuthorizationError, DomainConflictError
from src.shared_.database.database import get_session_factory

router = APIRouter(prefix="/api/identity/users", tags=["Identity:Users"])

async def provide_user_service() -> "UserService":
    """
    Assemble UserService using composition factories.
    Keeps construction consistent with the Tenants route.
    """
    session_factory = get_session_factory()
    password_hasher = build_password_hasher()
    return make_user_service(session_factory=session_factory, password_hasher=password_hasher)

@router.get("/me", response_model=UserRead)
async def me(current_user = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)

@router.post("", response_model=UserRead)
async def create_user(
    payload: UserCreate,
    request: Request,
    current_user = Depends(get_current_user),
    svc: UserService = Depends(provide_user_service),
) -> UserRead:
    """
    SUPER_ADMIN can create in any tenant.
    Other actors can create only inside their own tenant (and limited role as per policy).
    """
    try:
        user = await svc.create_user(
            requester=current_user,
            data=payload.model_dump(),
            correlation_id=request.headers.get("X-Correlation-ID"),
        )
        return UserRead.model_validate(user)
    except (DomainConflictError, AuthorizationError, NotFoundError) as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": str(e)})

@router.put(
    "/{user_id}/role",
    response_model=UserRead,
    dependencies=[Depends(require_role(Role.TENANT_ADMIN))],
)
async def change_role(
    user_id: str,
    new_role: str,
    request: Request,
    current_user = Depends(get_current_user),
    svc: UserService = Depends(provide_user_service),
) -> UserRead:
    try:
        user = await svc.change_user_role(
            requester=current_user,
            target_user_id=user_id,
            new_role=new_role,
            correlation_id=request.headers.get("X-Correlation-ID"),
        )
        return UserRead.model_validate(user)
    except (AuthorizationError, NotFoundError) as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": str(e)})