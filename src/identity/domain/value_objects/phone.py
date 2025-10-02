"""
Phone Number Value Object
"""
from __future__ import annotations

import re
from typing import Final

from shared.domain.base_value_object import BaseValueObject


# E.164 format: +[country code][number]
PHONE_REGEX: Final[str] = r'^\+[1-9]\d{1,14}$'


class Phone(BaseValueObject):
    """
    Phone number value object (E.164 format).
    
    Example: +919876543210
    """
    
    def __init__(self, value: str) -> None:
        normalized = value.strip()
        
        if not re.match(PHONE_REGEX, normalized):
            raise ValueError(
                f"Invalid phone format. Must be E.164 format (+country code + number): {value}"
            )
        
        self._value = normalized
    
    @property
    def value(self) -> str:
        return self._value
    
    def __str__(self) -> str:
        return self._value
    
    def _get_equality_components(self) -> tuple:
        return (self._value,)