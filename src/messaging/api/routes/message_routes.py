"""Message API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import Any, Dict, Optional, List
from uuid import UUID
from datetime import datetime, timedelta
import logging

from src.messaging.api.schemas.message_dto import (
    SendMessageRequest,
    BulkSendMessageRequest,
    MessageResponse,
    MessageListResponse,
    ConversationResponse
)
from src.messaging.application.services.message_service import MessageService
from src.messaging.infrastructure.dependencies import get_message_service
from src.shared_.api.dependencies import (
    get_current_user,
    check_permission,
    ensure_idempotency
)
from src.shared_.api.errors import ErrorResponse, error_response
from src.shared_.domain.auth import User, Permission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/messages",
    tags=["messages"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        429: {"model": ErrorResponse, "description": "Rate Limited"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)


@router.post(
    "/send",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a WhatsApp message",
    description="Queue a message for sending via WhatsApp"
)
async def send_message(
    channel_id: UUID,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.MESSAGE_SEND)),
    _idempotency: None = Depends(ensure_idempotency),
    service: MessageService = Depends(get_message_service)
):
    """Send a WhatsApp message."""
    try:
        logger.info(f"Sending message to {request.to_number} via channel {channel_id}")
        
        message = await service.send_message(
            tenant_id=user.tenant_id,
            channel_id=channel_id,
            to_number=request.to_number,
            content=request.content,
            template_name=request.template_name,
            template_variables=request.template_variables,
            media_url=request.media_url,
            idempotency_key=request.idempotency_key
        )
        
        return MessageResponse.model_validate(message, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Message validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to send message")
        )


@router.post(
    "/send-bulk",
    response_model=Dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send bulk WhatsApp messages",
    description="Queue multiple messages for sending"
)
async def send_bulk_messages(
    channel_id: UUID,
    request: BulkSendMessageRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.MESSAGE_SEND)),
    _idempotency: None = Depends(ensure_idempotency),
    service: MessageService = Depends(get_message_service)
):
    """Send messages in bulk."""
    try:
        logger.info(f"Sending bulk messages to {len(request.recipients)} recipients")
        
        results = await service.send_bulk_messages(
            tenant_id=user.tenant_id,
            channel_id=channel_id,
            recipients=request.recipients,
            content=request.content,
            template_name=request.template_name,
            template_variables_list=request.template_variables_list
        )
        
        return {
            "total": len(request.recipients),
            "queued": results["queued"],
            "failed": results["failed"],
            "message": f"Bulk send initiated for {results['queued']} messages"
        }
        
    except ValueError as e:
        logger.warning(f"Bulk send validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except Exception as e:
        logger.error(f"Failed to send bulk messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to send bulk messages")
        )


@router.get(
    "/",
    response_model=MessageListResponse,
    summary="List messages",
    description="Get a list of messages with optional filters"
)
async def list_messages(
    channel_id: Optional[UUID] = Query(None, description="Filter by channel"),
    direction: Optional[str] = Query(None, regex="^(inbound|outbound)$", description="Filter by direction"),
    status: Optional[str] = Query(None, description="Filter by status"),
    from_date: Optional[datetime] = Query(None, description="Filter messages from this date"),
    to_date: Optional[datetime] = Query(None, description="Filter messages until this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.MESSAGE_READ)),
    service: MessageService = Depends(get_message_service)
):
    """List messages with filters."""
    try:
        messages = await service.list_messages(
            tenant_id=user.tenant_id,
            channel_id=UUID(channel_id),
            direction=direction,
            limit=page_size,
        )
        
        total = await service.count_messages(
            tenant_id=user.tenant_id,
            channel_id=channel_id,
            direction=direction,
            status=status,
            from_date=from_date,
            to_date=to_date
        )
        
        return MessageListResponse(
            messages=[
                MessageResponse.model_validate(msg, from_attributes=True)
                for msg in messages
            ],
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total
        )
        
    except Exception as e:
        logger.error(f"Failed to list messages: {e}")
        raise HTTPException(
            status_code="",
            detail=error_response(500, "internal_error", "Failed to list messages")
        )


@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Get message details",
    description="Get detailed information about a specific message"
)
async def get_message(
    message_id: UUID = Path(..., description="Message UUID"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.MESSAGE_READ)),
    service: MessageService = Depends(get_message_service)
):
    """Get message details."""
    try:
        message = await service.get_message(message_id, user.tenant_id)
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response(404, "not_found", "Message not found")
            )
        
        return MessageResponse.model_validate(message, from_attributes=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to get message")
        )


@router.get(
    "/conversations/{phone_number}",
    response_model=ConversationResponse,
    summary="Get conversation thread",
    description="Get all messages in a conversation with a specific phone number"
)
async def get_conversation(
    phone_number: str = Path(..., description="Phone number in E.164 format"),
    channel_id: Optional[UUID] = Query(None, description="Filter by channel"),
    limit: int = Query(50, ge=1, le=200, description="Number of messages to retrieve"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.MESSAGE_READ)),
    service: MessageService = Depends(get_message_service)
):
    """Get conversation thread with a phone number."""
    try:
        conversation = await service.get_conversation(
            tenant_id=user.tenant_id,
            phone_number=phone_number,
            channel_id=channel_id,
            limit=limit
        )
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response(404, "not_found", "Conversation not found")
            )
        
        return ConversationResponse(**conversation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to get conversation")
        )


@router.post(
    "/{message_id}/retry",
    response_model=MessageResponse,
    summary="Retry failed message",
    description="Retry sending a failed message"
)
async def retry_message(
    message_id: UUID = Path(..., description="Message UUID"),
    user: User = Depends(get_current_user),
    _: None = Depends(lambda u=Depends(get_current_user): check_permission(u, Permission.MESSAGE_SEND)),
    service: MessageService = Depends(get_message_service)
):
    """Retry sending a failed message."""
    try:
        message = await service.retry_message(message_id, user.tenant_id)
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response(404, "not_found", "Message not found")
            )
        
        return MessageResponse.model_validate(message, from_attributes=True)
        
    except ValueError as e:
        logger.warning(f"Cannot retry message: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(400, "validation_error", str(e))
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(500, "internal_error", "Failed to retry message")
        )