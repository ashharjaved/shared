from abc import ABC, abstractmethod
from typing import Any, Dict, List


class WhatsAppGateway(ABC):
    """Gateway interface for WhatsApp Business API."""
    
    @abstractmethod
    async def send_message(
        self,
        phone_number_id: str,
        to: str,
        message_type: str,
        content: Dict[str, Any],
        access_token: str
    ) -> Dict[str, Any]:
        """Send a message via WhatsApp API."""
        pass
    
    @abstractmethod
    async def send_template_message(
        self,
        phone_number_id: str,
        to: str,
        template_name: str,
        language_code: str,
        components: List[Dict],
        access_token: str
    ) -> Dict[str, Any]:
        """Send a template message."""
        pass
    
    @abstractmethod
    async def get_media_url(
        self,
        media_id: str,
        access_token: str
    ) -> str:
        """Get media download URL."""
        pass
    
    @abstractmethod
    async def download_media(
        self,
        media_url: str,
        access_token: str
    ) -> bytes:
        """Download media file."""
        pass
    
    @abstractmethod
    async def upload_media(
        self,
        phone_number_id: str,
        file_data: bytes,
        mime_type: str,
        access_token: str
    ) -> str:
        """Upload media and get media ID."""
        pass