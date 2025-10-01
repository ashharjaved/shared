# src/identity/domain/value_objects/password_hash.py
"""Password hash value object."""

from dataclasses import dataclass

from ..exception import ValidationError


@dataclass(frozen=True, slots=True)
class PasswordHash:
    """Opaque wrapper for already-hashed password values."""
    
    value: str
    
    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("Password hash cannot be empty")
        
        # Basic validation - should look like a hash
        if len(self.value) < 32:
            raise ValidationError("Password hash appears invalid (too short)")
        
    @classmethod
    def from_hash(cls, hashed_value: str) -> "PasswordHash":
        if not isinstance(hashed_value, str) or not hashed_value:
            raise ValueError("invalid_hashed_password")
        return cls(hashed_value)
    
    def __str__(self) -> str:
        return "[REDACTED]"
    
    def __repr__(self) -> str:
        return f"PasswordHash([REDACTED])"
