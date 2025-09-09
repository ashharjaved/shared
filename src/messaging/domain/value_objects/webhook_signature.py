# src/messaging/domain/value_objects/webhook_signature.py
"""Webhook signature value object."""

from dataclasses import dataclass

from ..exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class WebhookSignature:
    """Immutable wrapper for webhook signature.
    
    Validates signature format but does not verify authenticity.
    """
    
    value: str
    
    def __post_init__(self) -> None:
        """Validate signature format on construction.
        
        Raises:
            ValidationError: If signature is invalid
            
        Examples:
            >>> sig = WebhookSignature("sha256=abc123")
            >>> sig.value
            'sha256=abc123'
            
            >>> WebhookSignature("")  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ValidationError: Signature cannot be empty
        """
        if not self.value:
            raise ValidationError("Signature cannot be empty")
        
        if not self.value.startswith("sha256="):
            raise ValidationError("Signature must start with 'sha256='")
        
        # Extract hex part after 'sha256='
        hex_part = self.value[7:]
        if not hex_part:
            raise ValidationError("Signature hash cannot be empty")
        
        # Validate hex format
        try:
            int(hex_part, 16)
        except ValueError:
            raise ValidationError("Signature hash must be valid hexadecimal")
    
    def get_hash(self) -> str:
        """Extract hash portion of signature.
        
        Returns:
            Hex hash without 'sha256=' prefix
            
        Examples:
            >>> sig = WebhookSignature("sha256=abc123")
            >>> sig.get_hash()
            'abc123'
        """
        return self.value[7:]
