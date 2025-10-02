"""
Base Value Object Contract for Domain Layer
Immutable objects defined by their attributes, not identity
"""
from __future__ import annotations

from abc import ABC
from typing import Any


class BaseValueObject(ABC):
    """
    Abstract base class for all value objects.
    
    Value objects are immutable and defined by their attributes.
    Two value objects are equal if all their attributes are equal.
    They have no identity (no id field).
    
    Subclasses should implement __init__ with all attributes as immutable.
    """
    
    def __eq__(self, other: object) -> bool:
        """Value objects are equal if all attributes match."""
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self) -> int:
        """Hash based on all attributes for use in sets/dicts."""
        return hash(tuple(sorted(self.__dict__.items())))
    
    def __repr__(self) -> str:
        """String representation showing class name and attributes."""
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{self.__class__.__name__}({attrs})"
    
    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevent modification after initialization.
        
        Raises:
            AttributeError: If attempting to modify after __init__
        """
        if hasattr(self, "_initialized"):
            raise AttributeError(
                f"Cannot modify immutable value object {self.__class__.__name__}"
            )
        super().__setattr__(name, value)
    
    def _finalize_init(self) -> None:
        """Call this at the end of __init__ in subclasses to freeze object."""
        super().__setattr__("_initialized", True)