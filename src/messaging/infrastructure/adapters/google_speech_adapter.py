"""Google Speech-to-Text adapter implementation."""

import logging
import httpx
from typing import Optional
import base64
import os

from src.messaging.domain.interfaces.external_services import SpeechToTextClient

logger = logging.getLogger(__name__)


class GoogleSpeechAdapter(SpeechToTextClient):
    """Google Cloud Speech-to-Text implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('GOOGLE_SPEECH_API_KEY')
        self.base_url = "https://speech.googleapis.com/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def transcribe_audio(
        self,
        audio_url: str,
        language_code: str = "en-US"
    ) -> Optional[str]:
        """Transcribe audio to text using Google Speech-to-Text."""
        try:
            # Download audio file
            audio_data = await self._download_audio(audio_url)
            if not audio_data:
                return None
            
            # Prepare request
            url = f"{self.base_url}/speech:recognize"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key
            }
            
            # Base64 encode audio
            audio_content = base64.b64encode(audio_data).decode('utf-8')
            
            payload = {
                "config": {
                    "encoding": "OGG_OPUS",  # WhatsApp voice notes format
                    "sampleRateHertz": 16000,
                    "languageCode": language_code,
                    "model": "latest_short",
                    "enableAutomaticPunctuation": True
                },
                "audio": {
                    "content": audio_content
                }
            }
            
            # Send request
            response = await self.client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                if results:
                    # Get the first alternative of the first result
                    transcript = results[0].get("alternatives", [{}])[0].get("transcript", "")
                    return transcript
                
                return None
            else:
                logger.error(f"Speech-to-Text API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            return None
    
    async def _download_audio(self, audio_url: str) -> Optional[bytes]:
        """Download audio file from URL."""
        try:
            response = await self.client.get(audio_url)
            if response.status_code == 200:
                return response.content
            return None
        except Exception as e:
            logger.error(f"Failed to download audio: {e}")
            return None
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up HTTP client."""
        await self.client.aclose()


class MockSpeechAdapter(SpeechToTextClient):
    """Mock implementation for testing."""
    
    async def transcribe_audio(
        self,
        audio_url: str,
        language_code: str = "en-US"
    ) -> Optional[str]:
        """Return mock transcription."""
        logger.info(f"Mock transcribing audio from {audio_url}")
        return "This is a mock transcription for testing purposes."