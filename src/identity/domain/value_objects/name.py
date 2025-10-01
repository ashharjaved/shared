
# src/identity/domain/value_objects/name.py
"""Name value object."""

from dataclasses import dataclass

from ..exception import ValidationError


@dataclass(frozen=True, slots=True)
class Name:
    """Non-empty trimmed name value object."""
    
    value: str
    
    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("Name cannot be empty")
        
        trimmed = self.value.strip()
        if not trimmed:
            raise ValidationError("Name cannot be only whitespace")
        
        if len(trimmed) > 255:
            raise ValidationError("Name cannot exceed 255 characters")
        
        # Update value if trimmed
        if trimmed != self.value:
            object.__setattr__(self, 'value', trimmed)
    
    def __str__(self) -> str:
        return self.value
