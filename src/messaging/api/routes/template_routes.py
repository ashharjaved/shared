"""Template management API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import Optional, List
from uuid import UUID
import logging

from src.messaging.api.schemas.template_dto import (
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateResponse,
    TemplateListResponse,
    TemplateSubmitRequest,
    TemplateTestRequest
)
from src.messaging.application.services.template_service import TemplateService
from src.messaging.infrastructure.dependencies import get_template_service
from src.shared_.api.dependencies import (
    get_current_user,
    check_permission,
    ensure_idempotency
)
from src.shared_.api.errors import ErrorResponse, error_response
from src.shared_.domain.auth import User, Permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/templates",
    tags=["templates"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)


@router.post(
    "/",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a message template",
    description="Create a new WhatsApp message template"
)
async def create_template(
    channel_id: UUID,
    request: TemplateCreateRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.TEMPLATE_CREATE)),
    _idempotency: None = Depends(ensure_idempotency),
    service: TemplateService = Depends(get_template_service)
):
    """Create a new message template."""
    try:
        logger.info(f"Creating template {request.name} for channel {channel_id}")
        
        template = await service.create_template(
            tenant_id=user.tenant_id,
            channel_id=channel_id,
            name=request.name,
            language=request.language,
            category=request.category,
            components=[comp.model_dump() for comp in request.components]
        )
        
        return TemplateResponse.model_validate(template, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Template validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to create template")
        )


@router.get(
    "/",
    response_model=TemplateListResponse,
    summary="List templates",
    description="Get a list of message templates"
)
async def list_templates(
    channel_id: Optional[UUID] = Query(None, description="Filter by channel"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.TEMPLATE_READ)),
    service: TemplateService = Depends(get_template_service)
):
    """List message templates."""
    try:
        templates = await service.list_templates(
            tenant_id=user.tenant_id,
            channel_id=channel_id,
            status_filter=status,
            category_filter=category
        )
        
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_templates = templates[start:end]
        
        return TemplateListResponse(
            templates=[
                TemplateResponse.model_validate(tpl, from_attributes=True)
                for tpl in paginated_templates
            ],
            total=len(templates),
            page=page,
            page_size=page_size,
            has_more=end < len(templates)
        )
        
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to list templates")
        )


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Get template details",
    description="Get detailed information about a specific template"
)
async def get_template(
    template_id: UUID = Path(..., description="Template UUID"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.TEMPLATE_READ)),
    service: TemplateService = Depends(get_template_service)
):
    """Get template details."""
    try:
        template = await service.get_template(template_id, user.tenant_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response(404, "not_found", "Template not found")
            )
        
        return TemplateResponse.model_validate(template, from_attributes=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to get template")
        )


@router.put(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Update template",
    description="Update a draft template"
)
async def update_template(
    template_id: UUID = Path(..., description="Template UUID"),
    request: TemplateUpdateRequest = ...,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.TEMPLATE_UPDATE)),
    _idempotency: None = Depends(ensure_idempotency),
    service: TemplateService = Depends(get_template_service)
):
    """Update a template (only drafts can be updated)."""
    try:
        template = await service.update_template(
            template_id=template_id,
            tenant_id=user.tenant_id,
            components=[comp.model_dump() for comp in request.components] if request.components else None,
            category=request.category
        )
        
        return TemplateResponse.model_validate(template, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Template update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to update template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to update template")
        )


@router.post(
    "/{template_id}/submit",
    response_model=TemplateResponse,
    summary="Submit template for approval",
    description="Submit a draft template to WhatsApp for approval"
)
async def submit_template(
    template_id: UUID = Path(..., description="Template UUID"),
    request: TemplateSubmitRequest = ...,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.TEMPLATE_UPDATE)),
    service: TemplateService = Depends(get_template_service)
):
    """Submit template for WhatsApp approval."""
    try:
        template = await service.submit_for_approval(
            template_id=template_id,
            tenant_id=user.tenant_id,
            business_id=request.business_id
        )
        
        return TemplateResponse.model_validate(template, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Template submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to submit template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to submit template")
        )


@router.post(
    "/{template_id}/test",
    response_model=MessageResponse,
    summary="Test a template",
    description="Send a test message using a template"
)
async def test_template(
    template_id: UUID = Path(..., description="Template UUID"),
    request: TemplateTestRequest = ...,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.MESSAGE_SEND)),
    service: TemplateService = Depends(get_template_service)
):
    """Test a template by sending a test message."""
    try:
        message = await service.test_template(
            template_id=template_id,
            tenant_id=user.tenant_id,
            to_number=request.to_number,
            variables=request.variables
        )
        
        return MessageResponse.model_validate(message, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Template test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to test template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to test template")
        )


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a template",
    description="Delete a draft template"
)
async def delete_template(
    template_id: UUID = Path(..., description="Template UUID"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.TEMPLATE_DELETE)),
    service: TemplateService = Depends(get_template_service)
):
    """Delete a template (only drafts can be deleted)."""
    try:
        await service.delete_template(template_id, user.tenant_id)
        return None
        
    except ValueError as e:
        logger.warning(f"Template deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to delete template")
        )