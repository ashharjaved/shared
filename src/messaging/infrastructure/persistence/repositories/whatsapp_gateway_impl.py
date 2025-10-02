"""
WhatsApp Cloud API Gateway Implementation
Adapter for Meta Graph API v18.0
"""
from typing import Dict, Any, List
import httpx

from src.messaging.domain.protocols.whatsapp_gateway_repository import WhatsAppGateway
from src.messaging.domain.exceptions import WhatsAppAPIError
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class WhatsAppGatewayImpl(WhatsAppGateway):
    """
    Concrete implementation of WhatsAppGateway using Meta Graph API.
    
    Circuit breaker and retry logic should wrap this adapter.
    """
    
    def __init__(self, api_url: str, api_version: str = "v18.0"):
        self.api_url = api_url.rstrip("/")
        self.api_version = api_version
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def send_text_message(
        self, phone_number_id: str, to: str, body: str
    ) -> Dict[str, Any]:
        """Send text message via WhatsApp Cloud API."""
        url = f"{self.api_url}/{self.api_version}/{phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body}
        }
        
        return await self._post(url, payload)
    
    async def send_template_message(
        self,
        phone_number_id: str,
        to: str,
        template_name: str,
        language_code: str,
        components: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Send template message with variable substitution."""
        url = f"{self.api_url}/{self.api_version}/{phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        
        return await self._post(url, payload)
    
    async def send_interactive_message(
        self, phone_number_id: str, to: str, interactive: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send interactive message (buttons, lists)."""
        url = f"{self.api_url}/{self.api_version}/{phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive
        }
        
        return await self._post(url, payload)
    
    async def get_message_templates(
        self, waba_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch message templates from WhatsApp."""
        url = f"{self.api_url}/{self.api_version}/{waba_id}/message_templates"
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error fetching templates: {e.response.text}")
            raise WhatsAppAPIError(
                error_message=f"Failed to fetch templates: {e.response.text}",
                error_code="template_fetch_failed",
            )
    
    async def create_template(
        self, waba_id: str, template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit new template for approval."""
        url = f"{self.api_url}/{self.api_version}/{waba_id}/message_templates"
        
        return await self._post(url, template)
    
    async def mark_message_read(
        self, phone_number_id: str, message_id: str
    ) -> bool:
        """Mark message as read."""
        url = f"{self.api_url}/{self.api_version}/{phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            await self._post(url, payload)
            return True
        except WhatsAppAPIError:
            return False
    
    async def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute POST request with error handling."""
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.text else {}
            error_code = error_data.get("error", {}).get("code", "unknown_error")
            error_message = error_data.get("error", {}).get("message", str(e))
            
            logger.error(
                f"WhatsApp API error: {error_code}",
                extra={"url": url, "status": e.response.status_code, "error": error_message}
            )
            
            raise WhatsAppAPIError(
                error_message=error_message,
                error_code=error_code
            )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()