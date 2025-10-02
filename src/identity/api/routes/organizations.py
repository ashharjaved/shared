"""
Organization Management Routes
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from shared.infrastructure.observability.logger import get_logger
from src.identity.api.schemas.organization_schemas import (
    CreateOrganizationRequest,
    OrganizationResponse,
)
from src.identity.api.dependencies import (
    get_current_active_user,
    require_roles,
    get_uow,
    CurrentUser,
)
from src.identity.application.commands.create_organization_command import (
    CreateOrganizationCommand,
    CreateOrganizationCommandHandler,
)
from src.identity.application.queries.get_organization_by_id_query import (
    GetOrganizationByIdQuery,
    GetOrganizationByIdQueryHandler,
)
from src.identity.infrastructure.adapters.identity_unit_of_work import IdentityUnitOfWork

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
    description="Create a new organization (SuperAdmin only)",
    dependencies=[Depends(require_roles("SuperAdmin"))],
)
async def create_organization(
    body: CreateOrganizationRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> OrganizationResponse:
    """
    Create a new organization.
    
    Requires SuperAdmin role.
    """
    command = CreateOrganizationCommand(
        name=body.name,
        slug=body.slug,
        industry=body.industry,
        timezone=body.timezone,
        language=body.language,
        created_by=current_user.user_id,
    )
    
    handler = CreateOrganizationCommandHandler(uow)
    result = await handler.handle(command)
    
    if result.is_failure():
        logger.warning(f"Organization creation failed: {result}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "organization_creation_failed",
                "message": result,
            },
        )
    
    org_id = result
    
    # Get created organization
    query = GetOrganizationByIdQuery(organization_id=org_id)
    query_handler = GetOrganizationByIdQueryHandler(uow)
    org_result = await query_handler.handle(query)
    
    if org_result.is_failure() or not org_result.value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": "Organization created but could not be retrieved",
            },
        )
    
    org_dto = org_result.value
    
    return OrganizationResponse(
        id=org_dto.id,
        name=org_dto.name,
        slug=org_dto.slug,
        industry=org_dto.industry,
        is_active=org_dto.is_active,
        timezone=org_dto.timezone,
        language=org_dto.language,
        created_at=org_dto.created_at,
    )


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Organization",
    description="Get organization by ID",
)
async def get_organization(
    organization_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> OrganizationResponse:
    """
    Get organization by ID.
    
    Users can only view their own organization.
    """
    # Enforce: users can only view their own organization
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": "You can only view your own organization",
            },
        )
    
    query = GetOrganizationByIdQuery(organization_id=organization_id)
    handler = GetOrganizationByIdQueryHandler(uow)
    result = await handler.handle(query)
    
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
                "message": f"Organization not found: {organization_id}",
            },
        )
    
    org_dto = result.value
    
    return OrganizationResponse(
        id=org_dto.id,
        name=org_dto.name,
        slug=org_dto.slug,
        industry=org_dto.industry,
        is_active=org_dto.is_active,
        timezone=org_dto.timezone,
        language=org_dto.language,
        created_at=org_dto.created_at,
    )


@router.get(
    "/me",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get My Organization",
    description="Get current user's organization",
)
async def get_my_organization(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    uow: Annotated[IdentityUnitOfWork, Depends(get_uow)],
) -> OrganizationResponse:
    """
    Get current user's organization.
    
    Convenience endpoint for /organizations/{organization_id}.
    """
    query = GetOrganizationByIdQuery(organization_id=current_user.organization_id)
    handler = GetOrganizationByIdQueryHandler(uow)
    result = await handler.handle(query)
    
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
                "message": "Organization not found",
            },
        )
    
    org_dto = result.value
    
    return OrganizationResponse(
        id=org_dto.id,
        name=org_dto.name,
        slug=org_dto.slug,
        industry=org_dto.industry,
        is_active=org_dto.is_active,
        timezone=org_dto.timezone,
        language=org_dto.language,
        created_at=org_dto.created_at,
    )