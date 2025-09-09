"""Message payload value object."""

from dataclasses import dataclass
from typing import Any, Dict
import json

from ..exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Payload:
    """Immutable wrapper for message payload data.
    
    Validates payload is non-empty and serializable.
    """
    
    data: Dict[str, Any]
    
    def __post_init__(self) -> None:
        """Validate payload on construction.
        
        Raises:
            ValidationError: If payload is empty or invalid
            
        Examples:
            >>> payload = Payload({"text": "Hello"})
            >>> payload.data
            {'text': 'Hello'}
            
            >>> Payload({})  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ValidationError: Payload cannot be empty
        """
        if not self.data:
            raise ValidationError("Payload cannot be empty")
        
        # Ensure payload is JSON serializable
        try:
            json.dumps(self.data)
        except (TypeError, ValueError) as e:
            raise ValidationError(f"Payload must be JSON serializable: {e}")
    
    def to_json(self) -> str:
        """Convert payload to JSON string.
        
        Returns:
            JSON representation of payload
            
        Examples:
            >>> payload = Payload({"text": "Hello"})
            >>> payload.to_json()
            '{"text": "Hello"}'
        """
        return json.dumps(self.data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Payload':
        """Create payload from JSON string.
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            Payload instance
            
        Raises:
            ValidationError: If JSON is invalid
            
        Examples:
            >>> payload = Payload.from_json('{"text": "Hello"}')
            >>> payload.data
            {'text': 'Hello'}
        """
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise ValidationError("Payload must be a JSON object")
            return cls(data)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON payload: {e}")

