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