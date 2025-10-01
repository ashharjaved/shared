"""Webhook API routes."""

from fastapi import APIRouter, Depends, Query, Header, Request, Response, HTTPException, status
from typing import Optional
import logging
import json

from src.messaging.api.schemas.webhook_dto import WebhookVerificationRequest, WebhookPayload
from src.messaging.application.services.webhook_service import WebhookService
from src.messaging.infrastructure.dependencies import get_webhook_service
from src.shared.api.errors import error_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks/whatsapp",
    tags=["webhooks"],
    include_in_schema=False  # Hide webhook endpoints from public API docs
)


@router.get("/{channel_id}")
async def verify_webhook(
    channel_id: str,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    service: WebhookService = Depends(get_webhook_service)
):
    """
    WhatsApp webhook verification endpoint.
    
    Called by WhatsApp to verify the webhook URL during setup.
    Must return the challenge string if verification is successful.
    """
    try:
        logger.info(f"Webhook verification request for channel {channel_id}")
        
        # Get expected token from channel configuration
        # In production, this should be fetched from the database
        expected_token = await service.get_channel_verify_token(channel_id)
        
        if not expected_token:
            logger.warning(f"Channel {channel_id} not found for webhook verification")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid channel"
            )
        
        # Verify the webhook
        challenge = await service.verify_webhook(
            hub_mode,
            hub_verify_token,
            hub_challenge,
            expected_token
        )
        
        if challenge:
            logger.info(f"Webhook verification successful for channel {channel_id}")
            return Response(content=challenge, media_type="text/plain")
        
        logger.warning(f"Webhook verification failed for channel {channel_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed"
        )


@router.post("/{channel_id}")
async def process_webhook(
    channel_id: str,
    request: Request,
    payload: WebhookPayload,
    x_hub_signature_256: Optional[str] = Header(None),
    service: WebhookService = Depends(get_webhook_service)
):
    """
    Process WhatsApp webhook events.
    
    Receives:
    - Inbound messages
    - Delivery status updates
    - Read receipts
    - Other WhatsApp events
    """
    try:
        logger.info(f"Webhook event received for channel {channel_id}")
        
        # Verify signature if provided
        if x_hub_signature_256:
            # Get raw body for signature verification
            body = await request.body()
            
            # Get app secret for this channel
            app_secret = await service.get_channel_app_secret(channel_id)
            
            if not app_secret:
                logger.warning(f"Channel {channel_id} not found for webhook processing")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid channel"
                )
            
            # Verify signature
            is_valid = await service.verify_signature(
                x_hub_signature_256,
                body,
                app_secret
            )
            
            if not is_valid:
                logger.warning(f"Invalid webhook signature for channel {channel_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )
        
        # Get tenant ID from channel
        tenant_id = await service.get_tenant_from_channel(channel_id)
        
        if not tenant_id:
            logger.warning(f"Tenant not found for channel {channel_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid channel configuration"
            )
        
        # Process the webhook payload
        await service.process_webhook(
            tenant_id,
            payload.model_dump()
        )
        
        # WhatsApp expects a 200 OK response
        return {"status": "success"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error for channel {channel_id}: {e}")
        # Don't expose internal errors to WhatsApp
        # Return 200 to prevent WhatsApp from retrying
        return {"status": "error"}


@router.post("/debug/{channel_id}")
async def debug_webhook(
    channel_id: str,
    payload: dict,
    service: WebhookService = Depends(get_webhook_service)
):
    """
    Debug endpoint for testing webhook processing.
    
    This endpoint bypasses signature verification and is only
    available in development mode.
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found"
        )
    
    try:
        logger.info(f"Debug webhook for channel {channel_id}")
        
        # Get tenant ID from channel
        tenant_id = await service.get_tenant_from_channel(channel_id)
        
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid channel"
            )
        
        # Process the webhook payload
        await service.process_webhook(tenant_id, payload)
        
        return {"status": "success", "debug": True}
        
    except Exception as e:
        logger.error(f"Debug webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )