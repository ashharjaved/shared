"""Phone number value object."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PhoneNumber:
    """
    Validated phone number in E.164 format.
    Immutable value object.
    """
    value: str
    
    def __post_init__(self):
        """Validate phone number format."""
        # E.164 format: +[country code][subscriber number]
        # Max 15 digits, starting with +
        pattern = r'^\+[1-9]\d{1,14}$'
        if not re.match(pattern, self.value):
            raise ValueError(f"Invalid phone number format: {self.value}")
    
    @property
    def country_code(self) -> str:
        """Extract country code from phone number."""
        # Simple extraction - would need country code table for accuracy
        if self.value.startswith('+1'):
            return '1'  # US/Canada
        elif self.value.startswith('+91'):
            return '91'  # India
        # Add more as needed
        return self.value[1:3]
    
    @property
    def masked(self) -> str:
        """Return masked version showing only last 4 digits."""
        if len(self.value) > 4:
            return f"***{self.value[-4:]}"
        return "****"
    
    def __str__(self) -> str:
        return self.value