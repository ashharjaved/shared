
# src/identity/domain/value_objects/slug.py
"""Slug value object."""

import re
from dataclasses import dataclass

from ..exception import ValidationError


@dataclass(frozen=True, slots=True)
class Slug:
    """URL-safe slug value object."""
    
    value: str
    
    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("Slug cannot be empty")
        
        # RFC 1123 hostname style: [a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?
        pattern = r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'
        if not re.match(pattern, self.value):
            raise ValidationError(
                f"Slug must be 1-63 chars, lowercase alphanumeric with hyphens: {self.value}"
            )
        
        if self.value.startswith('-') or self.value.endswith('-'):
            raise ValidationError(f"Slug cannot start or end with hyphen: {self.value}")
    
    @classmethod
    def from_name(cls, name: str) -> 'Slug':
        """Generate slug from name."""
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        
        if not slug:
            raise ValidationError(f"Cannot generate slug from name: {name}")
        
        return cls(slug[:63])  # Truncate if too long
    
    def __str__(self) -> str:
        return self.value
