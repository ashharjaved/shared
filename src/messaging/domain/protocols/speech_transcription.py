"""
Speech Transcription Protocol
Abstracts voice message transcription service.
"""
from abc import abstractmethod
from typing import Protocol, Optional


class SpeechTranscription(Protocol):
    """
    Protocol for voice message transcription.
    
    Isolates domain from Google Speech-to-Text or other providers.
    """
    
    @abstractmethod
    async def transcribe_audio(
        self, audio_url: str, language_code: Optional[str] = None
    ) -> str:
        """
        Transcribe audio from URL to text.
        
        Args:
            audio_url: URL to audio file (OGG, MP3, WAV)
            language_code: Optional language hint (en-US, hi-IN)
        
        Returns:
            Transcribed text
        
        Raises:
            TranscriptionError: If transcription fails
        """
        ...