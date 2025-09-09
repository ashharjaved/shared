# src/messaging/domain/value_objects/message_status.py
"""Message status value object."""

from enum import Enum


class MessageStatus(Enum):
    """Valid message status values with ordered progression."""
    
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    
    def can_transition_to(self, new_status: 'MessageStatus') -> bool:
        """Check if transition to new status is valid.
        
        Valid transitions:
        - queued -> sent, failed
        - sent -> delivered, failed
        - delivered -> read, failed
        - read -> (no transitions)
        - failed -> (no transitions)
        
        Args:
            new_status: Target status to transition to
            
        Returns:
            True if transition is valid, False otherwise
            
        Examples:
            >>> status = MessageStatus.QUEUED
            >>> status.can_transition_to(MessageStatus.SENT)
            True
            >>> status.can_transition_to(MessageStatus.READ)
            False
        """
        valid_transitions = {
            MessageStatus.QUEUED: {MessageStatus.SENT, MessageStatus.FAILED},
            MessageStatus.SENT: {MessageStatus.DELIVERED, MessageStatus.FAILED},
            MessageStatus.DELIVERED: {MessageStatus.READ, MessageStatus.FAILED},
            MessageStatus.READ: set(),
            MessageStatus.FAILED: set(),
        }
        
        return new_status in valid_transitions.get(self, set())
