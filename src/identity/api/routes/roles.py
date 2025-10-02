"""
Role Management Routes
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from shared.infrastructure.observability.logger import get_logger
from src.identity.api.schemas.role_schemas import (
    AssignRoleRequest,
    RevokeRoleRequest,
    RoleResponse,
    UserRolesResponse,
)
from src.identity.api.dependencies import (
    get_current_active_user,
    require_roles,
    get_uow,
    CurrentUser,
)
from src.identity.application.services.role_service import RoleService
from src.identity.infrastructure.adapters.identity_unit_of_work import IdentityUnitOfWork

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/assign",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Assign Role",
    description="Assign a role to a user",
    dependencies=[Depends(require_roles("TenantAdmin", "SuperAdmin"))],
)
async def assign_role(
    body: AssignRoleRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> dict:
    """
    Assign a role to a user.
    
    Requires TenantAdmin or SuperAdmin role.
    """
    role_service = RoleService(uow)
    
    result = await role_service.assign_role(
        user_id=UUID(body.user_id),
        role_id=UUID(body.role_id),
        organization_id=current_user.organization_id,
        assigned_by=current_user.user_id,
    )
    
    if result.is_failure():
        logger.warning(f"Role assignment failed: {result}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "role_assignment_failed",
                "message": result,
            },
        )
    
    return {"message": "Role assigned successfully"}


@router.post(
    "/revoke",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Revoke Role",
    description="Revoke a role from a user",
    dependencies=[Depends(require_roles("TenantAdmin", "SuperAdmin"))],
)
async def revoke_role(
    body: RevokeRoleRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> dict:
    """
    Revoke a role from a user.
    
    Requires TenantAdmin or SuperAdmin role.
    """
    role_service = RoleService(uow)
    
    result = await role_service.revoke_role(
        user_id=UUID(body.user_id),
        role_id=UUID(body.role_id),
        organization_id=current_user.organization_id,
        revoked_by=current_user.user_id,
    )
    
    if result.is_failure():
        logger.warning(f"Role revocation failed: {result}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "role_revocation_failed",
                "message": result,
            },
        )
    
    return {"message": "Role revoked successfully"}


@router.get(
    "/users/{user_id}",
    response_model=UserRolesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User Roles",
    description="Get all roles assigned to a user",
)
async def get_user_roles(
    user_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> UserRolesResponse:
    """
    Get all roles assigned to a user.
    
    Requires authentication. RLS ensures only same-org users visible.
    """
    role_service = RoleService(uow)
    
    result = await role_service.get_user_roles(
        user_id=user_id,
        organization_id=current_user.organization_id,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": result,
            },
        )
    
    roles_dto = result.value
    
    roles = [
        RoleResponse(
            id=r.id,
            organization_id=r.organization_id,
            name=r.name,
            description=r.description,
            permissions=r.permissions,
            is_system=r.is_system,
            created_at=r.created_at,
        )
        for r in roles_dto
    ]
    
    return UserRolesResponse(
        user_id=str(user_id),
        roles=roles,
    )