"""WhatsApp Business API adapter implementation."""

import httpx
import hmac
import hashlib
from typing import Dict, Any, Optional
import json
import logging

from src.messaging.domain.interfaces.external_services import (
    WhatsAppClient,
    WhatsAppMessageRequest,
    WhatsAppMessageResponse
)

logger = logging.getLogger(__name__)


class WhatsAppAPIAdapter(WhatsAppClient):
    """WhatsApp Business Cloud API implementation."""
    
    def __init__(self, base_url: str = "https://graph.facebook.com/v18.0"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def send_message(
        self,
        phone_number_id: str,
        access_token: str,
        request: WhatsAppMessageRequest
    ) -> WhatsAppMessageResponse:
        """Send message via WhatsApp API."""
        try:
            url = f"{self.base_url}/{phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build payload based on message type
            payload = self._build_message_payload(request)
            
            response = await self.client.post(
                url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return WhatsAppMessageResponse(
                    message_id=data["messages"][0]["id"],
                    success=True
                )
            else:
                error_data = response.json().get("error", {})
                return WhatsAppMessageResponse(
                    message_id="",
                    success=False,
                    error_code=str(error_data.get("code", response.status_code)),
                    error_message=error_data.get("message", "Unknown error")
                )
                
        except httpx.TimeoutException:
            logger.error(f"WhatsApp API timeout for number {phone_number_id}")
            return WhatsAppMessageResponse(
                message_id="",
                success=False,
                error_code="timeout",
                error_message="Request timeout"
            )
        except Exception as e:
            logger.error(f"WhatsApp API error: {e}")
            return WhatsAppMessageResponse(
                message_id="",
                success=False,
                error_code="internal_error",
                error_message=str(e)
            )
    
    def _build_message_payload(self, request: WhatsAppMessageRequest) -> Dict[str, Any]:
        """Build WhatsApp API message payload."""
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": request.to
        }

        if request.type == "text" and request.text:
            payload["type"] = "text"
            payload["text"] = {"body": request.text}
        elif request.type == "template":
            payload["type"] = "template"
            template_payload: Dict[str, Any] = {
                "name": request.template_name,
                "language": {"code": request.template_language or "en"}
            }
            if request.template_components:
                template_payload["components"] = request.template_components
            payload["template"] = template_payload
        elif request.type == "image" and request.media_url:
            payload["type"] = "image"
            payload["image"] = {"link": request.media_url}

        # Add more message types as needed

        return payload
    
    async def verify_webhook_signature(
        self,
        signature: str,
        payload: bytes,
        app_secret: str
    ) -> bool:
        """Verify webhook signature using HMAC SHA256."""
        try:
            # WhatsApp sends signature as "sha256=<hash>"
            if not signature.startswith("sha256="):
                return False
            
            expected_hash = signature[7:]  # Remove "sha256=" prefix
            
            # Calculate HMAC
            mac = hmac.new(
                app_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            )
            calculated_hash = mac.hexdigest()
            
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(expected_hash, calculated_hash)
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    async def get_media_url(
        self,
        media_id: str,
        access_token: str
    ) -> Optional[str]:
        """Get media download URL from WhatsApp."""
        try:
            url = f"{self.base_url}/{media_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = await self.client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("url")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get media URL: {e}")
            return None
    
    async def submit_template(
        self,
        business_id: str,
        access_token: str,
        template_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit template for WhatsApp approval."""
        try:
            url = f"{self.base_url}/{business_id}/message_templates"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = await self.client.post(
                url,
                headers=headers,
                json=template_data
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Template submission error: {e}")
            return {"error": str(e)}
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up HTTP client."""
        await self.client.aclose()
