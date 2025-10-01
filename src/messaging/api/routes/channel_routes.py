"""Channel management API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import Optional
from uuid import UUID
import logging

from src.messaging.api.schemas.channel_dto import (
    ChannelCreateRequest,
    ChannelUpdateRequest,
    ChannelResponse,
    ChannelListResponse,
    ChannelStatsResponse
)
from src.messaging.application.services.channel_service import ChannelService
from src.messaging.infrastructure.dependencies import get_channel_service
from src.shared.api.dependencies import (
    get_current_user,
    check_permission,
    ensure_idempotency
)
from src.shared.errors import Err ErrorResponse, error_response
from src.shared.domain.auth import User, Permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/channels",
    tags=["channels"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)


@router.post(
    "/",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new WhatsApp channel",
    description="Create and register a new WhatsApp Business API channel for the tenant"
)
async def create_channel(
    request: ChannelCreateRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.CHANNEL_CREATE)),
    _idempotency: None = Depends(ensure_idempotency),
    service: ChannelService = Depends(get_channel_service)
):
    """Create a new WhatsApp channel."""
    try:
        logger.info(f"Creating channel for tenant {user.tenant_id}")
        
        channel = await service.create_channel(
            tenant_id=user.tenant_id,
            name=request.name,
            phone_number_id=request.phone_number_id,
            business_phone=request.business_phone,
            access_token=request.access_token,
            rate_limit=request.rate_limit_per_second,
            monthly_limit=request.monthly_message_limit
        )
        
        return ChannelResponse.model_validate(channel, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Channel validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to create channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to create channel")
        )


@router.get(
    "/",
    response_model=ChannelListResponse,
    summary="List all channels",
    description="Get a list of all WhatsApp channels for the tenant"
)
async def list_channels(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.CHANNEL_READ)),
    service: ChannelService = Depends(get_channel_service)
):
    """List all channels for the tenant."""
    try:
        channels = await service.list_channels(user.tenant_id)
        
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_channels = channels[start:end]
        
        return ChannelListResponse(
            channels=[
                ChannelResponse.model_validate(ch, from_attributes=True)
                for ch in paginated_channels
            ],
            total=len(channels),
            page=page,
            page_size=page_size,
            has_more=end < len(channels)
        )
        
    except Exception as e:
        logger.error(f"Failed to list channels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to list channels")
        )


@router.get(
    "/{channel_id}",
    response_model=ChannelResponse,
    summary="Get channel details",
    description="Get detailed information about a specific channel"
)
async def get_channel(
    channel_id: UUID = Path(..., description="Channel UUID"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.CHANNEL_READ)),
    service: ChannelService = Depends(get_channel_service)
):
    """Get channel details."""
    try:
        channel = await service.get_channel(channel_id, user.tenant_id)
        
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response(404, "not_found", "Channel not found")
            )
        
        return ChannelResponse.model_validate(channel, from_attributes=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to get channel")
        )


@router.put(
    "/{channel_id}",
    response_model=ChannelResponse,
    summary="Update channel configuration",
    description="Update channel settings such as rate limits or access token"
)
async def update_channel(
    channel_id: UUID = Path(..., description="Channel UUID"),
    request= ChannelUpdateRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.CHANNEL_UPDATE)),
    _idempotency: None = Depends(ensure_idempotency),
    service: ChannelService = Depends(get_channel_service)
):
    """Update channel configuration."""
    try:
        channel = await service.update_channel(
            channel_id=channel_id,
            tenant_id=user.tenant_id,
            name=request.name,
            access_token=request.access_token,
            rate_limit=request.rate_limit_per_second,
            monthly_limit=request.monthly_message_limit
        )
        
        return ChannelResponse.model_validate(channel, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Channel update validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to update channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to update channel")
        )


@router.delete(
    "/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a channel",
    description="Deactivate a WhatsApp channel (soft delete)"
)
async def delete_channel(
    channel_id: UUID = Path(..., description="Channel UUID"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.CHANNEL_DELETE)),
    service: ChannelService = Depends(get_channel_service)
):
    """Deactivate a channel."""
    try:
        await service.deactivate_channel(channel_id, user.tenant_id)
        return None
        
    except ValueError as e:
        logger.warning(f"Channel not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(404, "not_found", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to delete channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to delete channel")
        )


@router.get(
    "/{channel_id}/stats",
    response_model=ChannelStatsResponse,
    summary="Get channel statistics",
    description="Get usage statistics for a channel"
)
async def get_channel_stats(
    channel_id: UUID = Path(..., description="Channel UUID"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.CHANNEL_READ)),
    service: ChannelService = Depends(get_channel_service)
):
    """Get channel statistics."""
    try:
        stats = await service.get_channel_stats(channel_id, user.tenant_id)
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response(404, "not_found", "Channel not found")
            )
        
        return ChannelStatsResponse(**stats)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get channel stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to get channel statistics")
        )