# src/identity/domain/value_objects/email.py
"""Email value object."""

import re
from dataclasses import dataclass
from typing import Self

from ..exception import ValidationError


@dataclass(frozen=True, slots=True)
class Email:
    """Email address value object with RFC-lite validation."""
    
    value: str
    
    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("Email cannot be empty")
        
        normalized = self.value.lower().strip()
        if normalized != self.value:
            # Use object.__setattr__ to modify frozen dataclass
            object.__setattr__(self, 'value', normalized)
        
        # RFC-lite email validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, self.value):
            raise ValidationError(f"Invalid email format: {self.value}")
        
        if len(self.value) > 254:  # RFC 5321 limit
            raise ValidationError("Email address too long")
    
    @classmethod
    def from_string(cls, email: str) -> Self:
        """Create Email from string with normalization."""
        return cls(email.lower().strip())
    
    def domain(self) -> str:
        """Extract domain part of email."""
        return self.value.split('@')[1]

    
    def __str__(self) -> str:
        return self.value
    