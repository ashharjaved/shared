# src/conversation/domain/services/nlp_service.py
"""NLP service protocol for intent recognition."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class IntentResult:
    """NLP intent recognition result."""
    
    intent: str
    confidence: float
    entities: Dict[str, Any]
    language: Optional[str] = None


class NLPService(ABC):
    """Protocol for NLP intent recognition."""
    
    @abstractmethod
    async def detect_intent(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None
    ) -> Optional[IntentResult]:
        """
        Detect user intent from text.
        
        Returns None if confidence below threshold or no match.
        """
        pass
    
    @abstractmethod
    async def detect_language(self, text: str) -> Optional[str]:
        """Detect language from text. Returns ISO 639-1 code."""
        pass
    
    @abstractmethod
    async def extract_entities(
        self,
        text: str,
        entity_types: List[str],
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract named entities from text."""
        pass