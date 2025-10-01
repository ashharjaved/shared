"""External service interfaces."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class WhatsAppMessageRequest:
    """Request to send WhatsApp message."""
    to: str
    type: str  # text, template, interactive, etc.
    text: Optional[str] = None
    template_name: Optional[str] = None
    template_language: Optional[str] = None
    template_components: Optional[List[Dict[str, Any]]] = None
    media_url: Optional[str] = None


@dataclass
class WhatsAppMessageResponse:
    """Response from WhatsApp API."""
    message_id: str
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class WhatsAppClient(ABC):
    """Interface for WhatsApp Business API client."""
    
    @abstractmethod
    async def send_message(
        self,
        phone_number_id: str,
        access_token: str,
        request: WhatsAppMessageRequest
    ) -> WhatsAppMessageResponse:
        """Send a message via WhatsApp API."""
        pass
    
    @abstractmethod
    async def verify_webhook_signature(
        self,
        signature: str,
        payload: bytes,
        app_secret: str
    ) -> bool:
        """Verify webhook signature."""
        pass
    
    @abstractmethod
    async def get_media_url(
        self,
        media_id: str,
        access_token: str
    ) -> Optional[str]:
        """Get media download URL."""
        pass
    
    @abstractmethod
    async def submit_template(
        self,
        business_id: str,
        access_token: str,
        template_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit template for approval."""
        pass


class SpeechToTextClient(ABC):
    """Interface for speech transcription service."""
    
    @abstractmethod
    async def transcribe_audio(
        self,
        audio_url: str,
        language_code: str = "en-US"
    ) -> Optional[str]:
        """Transcribe audio to text."""
        pass


class EncryptionService(ABC):
    """Interface for encryption service."""
    
    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """Encrypt sensitive data."""
        pass
    
    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt sensitive data."""
        pass