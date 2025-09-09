# src/messaging/domain/value_objects/usage_window.py
"""Usage window value object for rate limiting and quotas."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from ..exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class UsageWindow:
    """Immutable window for tracking usage over time.
    
    Used for rate limiting and quota calculations.
    """
    
    start: datetime
    end: datetime
    current_count: int = 0
    limit: Optional[int] = None
    
    def __post_init__(self) -> None:
        """Validate window on construction.
        
        Raises:
            ValidationError: If window is invalid
            
        Examples:
            >>> start = datetime(2025, 1, 1, 12, 0)
            >>> end = datetime(2025, 1, 1, 13, 0)
            >>> window = UsageWindow(start, end, current_count=5, limit=100)
            >>> window.duration()
            datetime.timedelta(seconds=3600)
        """
        if self.start >= self.end:
            raise ValidationError("Window start must be before end")
        
        if self.current_count < 0:
            raise ValidationError("Current count cannot be negative")
        
        if self.limit is not None and self.limit < 0:
            raise ValidationError("Limit cannot be negative")
    
    def duration(self) -> timedelta:
        """Get window duration.
        
        Returns:
            Duration of the window
            
        Examples:
            >>> start = datetime(2025, 1, 1, 12, 0)
            >>> end = datetime(2025, 1, 1, 13, 0)
            >>> window = UsageWindow(start, end)
            >>> window.duration()
            datetime.timedelta(seconds=3600)
        """
        return self.end - self.start
    
    def is_within_limit(self) -> bool:
        """Check if current usage is within limit.
        
        Returns:
            True if within limit or no limit set
            
        Examples:
            >>> start = datetime(2025, 1, 1)
            >>> end = datetime(2025, 1, 2)
            >>> window = UsageWindow(start, end, current_count=5, limit=10)
            >>> window.is_within_limit()
            True
            
            >>> window = UsageWindow(start, end, current_count=15, limit=10)
            >>> window.is_within_limit()
            False
        """
        if self.limit is None:
            return True
        return self.current_count <= self.limit
    
    def would_exceed_limit(self, additional: int) -> bool:
        """Check if additional usage would exceed limit.
        
        Args:
            additional: Additional count to check
            
        Returns:
            True if would exceed limit
            
        Examples:
            >>> start = datetime(2025, 1, 1)
            >>> end = datetime(2025, 1, 2)
            >>> window = UsageWindow(start, end, current_count=8, limit=10)
            >>> window.would_exceed_limit(2)
            False
            >>> window.would_exceed_limit(3)
            True
        """
        if self.limit is None:
            return False
        return (self.current_count + additional) > self.limit
    
    def with_additional_usage(self, additional: int) -> 'UsageWindow':
        """Create new window with additional usage.
        
        Args:
            additional: Additional count to add
            
        Returns:
            New UsageWindow with updated count
            
        Examples:
            >>> start = datetime(2025, 1, 1)
            >>> end = datetime(2025, 1, 2)
            >>> window = UsageWindow(start, end, current_count=5, limit=10)
            >>> new_window = window.with_additional_usage(2)
            >>> new_window.current_count
            7
        """
        return UsageWindow(
            start=self.start,
            end=self.end,
            current_count=self.current_count + additional,
            limit=self.limit
        )
    
    def contains_time(self, timestamp: datetime) -> bool:
        """Check if timestamp falls within window.
        
        Args:
            timestamp: Timestamp to check
            
        Returns:
            True if timestamp is within window
            
        Examples:
            >>> start = datetime(2025, 1, 1, 12, 0)
            >>> end = datetime(2025, 1, 1, 13, 0)
            >>> window = UsageWindow(start, end)
            >>> window.contains_time(datetime(2025, 1, 1, 12, 30))
            True
            >>> window.contains_time(datetime(2025, 1, 1, 14, 0))
            False
        """
        return self.start <= timestamp < self.end