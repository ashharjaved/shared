"""
User Management Routes
"""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException, status, Query

from shared.infrastructure.observability.logger import get_logger
from src.identity.api.schemas.user_schemas import (
    CreateUserRequest,
    UserResponse,
    UserListResponse,
    DeactivateUserRequest,
)
from src.identity.api.dependencies import (
    get_current_active_user,
    require_roles,
    get_uow,
    CurrentUser,
)
from src.identity.application.services.user_service import UserService
from src.identity.infrastructure.adapters.identity_unit_of_work import IdentityUnitOfWork

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
    description="Create a new user in the organization",
    dependencies=[Depends(require_roles("TenantAdmin", "SuperAdmin"))],
)
async def create_user(
    body: CreateUserRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> UserResponse:
    """
    Create a new user.
    
    Requires TenantAdmin or SuperAdmin role.
    """
    user_service = UserService(uow)
    
    result = await user_service.create_user(
        organization_id=current_user.organization_id,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone=body.phone,
        created_by=current_user.user_id,
    )
    
    if result.is_failure():
        logger.warning(f"User creation failed: {result.error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "user_creation_failed",
                "message": result.error,
            },
        )
    
    user_id = result
    
    # Get created user
    user_result = await user_service.get_user_by_id(
        user_id=UUID(user_id),
        organization_id=current_user.organization_id,
    )
    
    if user_result.is_failure() or not user_result.value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": "User created but could not be retrieved",
            },
        )
    
    user_dto = user_result.value
    
    return UserResponse(
        id=user_dto.id,
        organization_id=user_dto.organization_id,
        email=user_dto.email,
        full_name=user_dto.full_name,
        phone=user_dto.phone,
        is_active=user_dto.is_active,
        email_verified=user_dto.email_verified,
        phone_verified=user_dto.phone_verified,
        last_login_at=user_dto.last_login_at,
        created_at=user_dto.created_at,
    )


@router.get(
    "",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Users",
    description="Get paginated list of users in organization",
)
async def list_users(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> UserListResponse:
    """
    List users in organization with pagination.
    
    Requires authentication.
    """
    user_service = UserService(uow)
    
    result = await user_service.list_users(
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": result.error,
            },
        )
    
    list_dto = result.value
    
    users = [
        UserResponse(
            id=u.id,
            organization_id=u.organization_id,
            email=u.email,
            full_name=u.full_name,
            phone=u.phone,
            is_active=u.is_active,
            email_verified=u.email_verified,
            phone_verified=u.phone_verified,
            last_login_at=u.last_login_at,
            created_at=u.created_at,
        )
        for u in list_dto.users
    ]
    
    return UserListResponse(
        users=users,
        total=list_dto.total,
        skip=list_dto.skip,
        limit=list_dto.limit,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User",
    description="Get user by ID",
)
async def get_user(
    user_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> UserResponse:
    """
    Get user by ID.
    
    Requires authentication. RLS ensures only same-org users visible.
    """
    user_service = UserService(uow)
    
    result = await user_service.get_user_by_id(
        user_id=user_id,
        organization_id=current_user.organization_id,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": result.error,
            },
        )
    
    if not result.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"User not found: {user_id}",
            },
        )
    
    user_dto = result.value
    
    return UserResponse(
        id=user_dto.id,
        organization_id=user_dto.organization_id,
        email=user_dto.email,
        full_name=user_dto.full_name,
        phone=user_dto.phone,
        is_active=user_dto.is_active,
        email_verified=user_dto.email_verified,
        phone_verified=user_dto.phone_verified,
        last_login_at=user_dto.last_login_at,
        created_at=user_dto.created_at,
    )


@router.post(
    "/{user_id}/deactivate",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Deactivate User",
    description="Deactivate a user account",
    dependencies=[Depends(require_roles("TenantAdmin", "SuperAdmin"))],
)
async def deactivate_user(
    user_id: UUID,
    body: DeactivateUserRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> dict:
    """
    Deactivate a user account.
    
    Requires TenantAdmin or SuperAdmin role.
    Revokes all active sessions.
    """
    user_service = UserService(uow)
    
    result = await user_service.deactivate_user(
        user_id=user_id,
        organization_id=current_user.organization_id,
        deactivated_by=current_user.user_id,
        reason=body.reason,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "deactivation_failed",
                "message": result.error,
            },
        )
    
    return {"message": "User deactivated successfully"}


@router.post(
    "/{user_id}/reactivate",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Reactivate User",
    description="Reactivate a deactivated user account",
    dependencies=[Depends(require_roles("TenantAdmin", "SuperAdmin"))],
)
async def reactivate_user(
    user_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> dict:
    """
    Reactivate a deactivated user account.
    
    Requires TenantAdmin or SuperAdmin role.
    """
    user_service = UserService(uow)
    
    result = await user_service.reactivate_user(
        user_id=user_id,
        organization_id=current_user.organization_id,
        reactivated_by=current_user.user_id,
    )
    
    if result.is_failure():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "reactivation_failed",
                "message": result.error,
            },
        )
    
    return {"message": "User reactivated successfully"}