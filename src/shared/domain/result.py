"""
Result Monad for Domain Operations
Represents success or failure without exceptions
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Success(Generic[T]):
    """
    Represents a successful operation result.
    
    Attributes:
        value: The successful result value
    """
    
    value: T
    
    def is_success(self) -> bool:
        """Always returns True for Success."""
        return True
    
    def is_failure(self) -> bool:
        """Always returns False for Success."""
        return False
    
    def map(self, func: Callable[[T], Any]) -> Success[Any] | Failure[Any]:
        """
        Transform the success value using the provided function.
        
        Args:
            func: Function to transform the value
            
        Returns:
            New Success with transformed value, or Failure if func raises
        """
        try:
            return Success(func(self.value))
        except Exception as e:
            return Failure(str(e))
    
    def flat_map(self, func: Callable[[T], Success[Any] | Failure[Any]]) -> Success[Any] | Failure[Any]:
        """
        Chain operations that return Results.
        
        Args:
            func: Function that returns a Result
            
        Returns:
            Result from applying func to the value
        """
        return func(self.value)
    
    def or_else(self, default: T) -> T:
        """Return the value (ignores default)."""
        return self.value
    
    def unwrap(self) -> T:
        """Return the value."""
        return self.value


@dataclass(frozen=True)
class Failure(Generic[E]):
    """
    Represents a failed operation result.
    
    Attributes:
        error: The error or error message
    """
    
    error: E
    
    def is_success(self) -> bool:
        """Always returns False for Failure."""
        return False
    
    def is_failure(self) -> bool:
        """Always returns True for Failure."""
        return True
    
    def map(self, func: Callable[[Any], Any]) -> Failure[E]:
        """
        Does nothing for Failure (error propagates).
        
        Args:
            func: Ignored function
            
        Returns:
            Self (unchanged)
        """
        return self
    
    def flat_map(self, func: Callable[[Any], Any]) -> Failure[E]:
        """
        Does nothing for Failure (error propagates).
        
        Args:
            func: Ignored function
            
        Returns:
            Self (unchanged)
        """
        return self
    
    def or_else(self, default: Any) -> Any:
        """Return the default value instead of error."""
        return default
    
    def unwrap(self) -> None:
        """
        Raise an exception with the error.
        
        Raises:
            ValueError: With the error message
        """
        raise ValueError(f"Attempted to unwrap a Failure: {self.error}")


# Type alias for Result
Result = Success[T] | Failure[E]