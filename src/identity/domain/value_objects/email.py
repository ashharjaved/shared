"""
Email Value Object
"""
from __future__ import annotations

import re
from typing import Final

from shared.domain.base_value_object import BaseValueObject


EMAIL_REGEX: Final[str] = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


class Email(BaseValueObject):
    """
    Email address value object with validation.
    
    Ensures email format is valid and normalizes to lowercase.
    """
    
    def __init__(self, value: str) -> None:
        normalized = value.lower().strip()
        
        if not re.match(EMAIL_REGEX, normalized):
            raise ValueError(f"Invalid email format: {value}")
        
        self._value = normalized
    
    @property
    def value(self) -> str:
        return self._value
    
    def __str__(self) -> str:
        return self._value
    
    def _get_equality_components(self) -> tuple:
        return (self._value,)