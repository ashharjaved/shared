# src/modules/whatsapp/domain/value_objects/phone_number.py
"""
Phone Number Value Object
Represents WhatsApp-compatible phone number in E.164 format
"""
from __future__ import annotations

import re
from typing import Any

from src.shared.domain.base_value_object import BaseValueObject


class PhoneNumber(BaseValueObject):
    """
    E.164 formatted phone number (e.g., +919876543210).
    
    WhatsApp requires E.164 format:
    - Starts with +
    - Country code (1-3 digits)
    - National number (up to 15 digits total)
    
    Examples:
        +14155552671 (US)
        +919876543210 (India)
        +442071838750 (UK)
    """
    
    E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")
    
    def __init__(self, value: str) -> None:
        """
        Initialize phone number with validation.
        
        Args:
            value: Phone number string
            
        Raises:
            ValueError: If phone number format is invalid
        """
        cleaned = value.strip()
        
        if not self.E164_PATTERN.match(cleaned):
            raise ValueError(
                f"Invalid phone number format: {value}. "
                f"Must be E.164 format (e.g., +919876543210)"
            )
        
        super().__setattr__("_value", cleaned)
        self._finalize_init()
    
    @property
    def value(self) -> str:
        """Get the phone number string."""
        return self.value
    
    @property
    def country_code(self) -> str:
        """Extract country code (including +)."""
        # Simple heuristic: 1-3 digits after +
        for i in range(2, 5):  # +1, +91, +442
            if len(self.value) > i:
                return self.value[:i]
        return self.value[:2]
    
    @property
    def national_number(self) -> str:
        """Get number without country code."""
        return self.value[len(self.country_code):]
    
    def __str__(self) -> str:
        """String representation."""
        return self.value