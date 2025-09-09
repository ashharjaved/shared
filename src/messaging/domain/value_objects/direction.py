# src/messaging/domain/value_objects/direction.py
"""Message direction value object."""

from enum import Enum


class Direction(Enum):
    """Message direction - inbound or outbound."""
    
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    
    def __str__(self) -> str:
        return self.value

    def is_inbound(self) -> bool:
        """Check if direction is inbound.
        
        Returns:
            True if message is inbound
            
        Examples:
            >>> Direction.IN.is_inbound()
            True
            >>> Direction.OUT.is_inbound()
            False
        """
        return self == Direction.INBOUND
    
    def is_outbound(self) -> bool:
        """Check if direction is outbound.
        
        Returns:
            True if message is outbound
            
        Examples:
            >>> Direction.OUT.is_outbound()
            True
            >>> Direction.IN.is_outbound()
            False
        """
        return self == Direction.OUTBOUND
    
    def opposite(self) -> "Direction":
        return Direction.OUTBOUND if self is Direction.INBOUND else Direction.INBOUND