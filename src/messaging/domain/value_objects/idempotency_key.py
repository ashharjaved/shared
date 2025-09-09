# src/messaging/domain/value_objects/idempotency_key.py
"""Idempotency key value object."""

from dataclasses import dataclass
from typing import Optional
import hashlib

from ..exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Immutable wrapper for idempotency keys.
    
    Can be created from WhatsApp message ID or custom client key.
    """

    value: str
    MAX_LEN: int = 255

    def __post_init__(self) -> None:
        """Validate key on construction.
        
        Raises:
            ValidationError: If key is invalid
            
        Examples:
            >>> key = IdempotencyKey("wa_msg_123")
            >>> key.value
            'wa_msg_123'
            
            >>> IdempotencyKey("")  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ValidationError: Idempotency key cannot be empty
        """
        v = self.value.strip()
        object.__setattr__(self, "value", v)
        if not v:
            raise ValidationError("Idempotency key cannot be empty")
        
        if len(v) > self.MAX_LEN:
            raise ValidationError("Idempotency key cannot exceed 255 characters")
        if any(ord(c) < 32 for c in v):
            raise ValidationError("Idempotency key contains invalid control characters")
    
    @classmethod
    def from_wa_message_id(cls, wa_message_id: str) -> 'IdempotencyKey':
        """Create key from WhatsApp message ID.
        
        Args:
            wa_message_id: WhatsApp message identifier
            
        Returns:
            IdempotencyKey instance
            
        Examples:
            >>> key = IdempotencyKey.from_wa_message_id("wamid.123")
            >>> key.value
            'wamid.123'
        """
        return cls(wa_message_id.strip())
    
    @classmethod
    def from_client_key(cls, tenant_id: str, operation: str, key: str) -> 'IdempotencyKey':
        """Create key from client-provided components.
        
        Args:
            tenant_id: Tenant identifier
            operation: Operation name (e.g., 'send_message')
            key: Client-provided key
            
        Returns:
            IdempotencyKey instance with hashed composite key
            
        Examples:
            >>> key = IdempotencyKey.from_client_key("tenant1", "send", "key123")
            >>> len(key.value)
            64
        """
        composite = f"{tenant_id}:{operation}:{key}"
        # Hash to ensure consistent length and avoid issues with special chars
        hash_value = hashlib.sha256(composite.encode()).hexdigest()
        return cls(hash_value)
    
    @classmethod
    def from_content_hash(cls, content: str) -> 'IdempotencyKey':
        """Create key from content hash for duplicate detection.
        
        Args:
            content: Content to hash
            
        Returns:
            IdempotencyKey instance
            
        Examples:
            >>> key = IdempotencyKey.from_content_hash("hello world")
            >>> len(key.value)
            64
        """
        hash_value = hashlib.sha256(content.encode()).hexdigest()
        return cls(hash_value)
    
    def __str__(self) -> str:
        return self.value

    def as_header(self) -> tuple[str, str]:
        """Standard header pair for transport layers."""
        return ("Idempotency-Key", self.value)