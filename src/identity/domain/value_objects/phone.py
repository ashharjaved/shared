# src/identity/domain/value_objects/phone.py
"""Phone value object."""

import re
from dataclasses import dataclass
from typing import Self

from ..exception import ValidationError


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """E.164 formatted phone number value object."""
    
    value: str
    
    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("Phone cannot be empty")
        
        # E.164 format: +1234567890 (1-15 digits)
        pattern = r'^\+[1-9]\d{1,14}$'
        if not re.match(pattern, self.value):
            raise ValidationError(f"Phone must be in E.164 format (+1234567890): {self.value}")
    
    @classmethod
    def from_string(cls, phone: str) -> Self:
        """Create Phone from string, adding + if missing."""
        phone = phone.strip()
        if not phone.startswith('+'):
            phone = '+' + phone
        return cls(phone)
    
    def __str__(self) -> str:
        return self.value
