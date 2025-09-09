# src/identity/domain/services/subscription_rules.py
"""Subscription lifecycle rules domain service."""

from ..types import SubscriptionStatus
from ..errors import ValidationError

class SubscriptionRules:
    """Business rules for subscription lifecycle transitions."""
    
    # Valid state transitions
    VALID_TRANSITIONS: dict[SubscriptionStatus, set[SubscriptionStatus]] = {
        'trial': {'active', 'past_due', 'cancelled', 'expired'},
        'active': {'past_due', 'cancelled', 'expired'},
        'past_due': {'active', 'cancelled', 'expired'},
        'cancelled': set(),  # Terminal state
        'expired': set(),    # Terminal state
    }
    
    @classmethod
    def can_transition_to(
        cls, 
        from_status: SubscriptionStatus, 
        to_status: SubscriptionStatus
    ) -> bool:
        """Check if transition between statuses is valid."""
        return to_status in cls.VALID_TRANSITIONS.get(from_status, set())
    
    @classmethod
    def require_valid_transition(
        cls, 
        from_status: SubscriptionStatus, 
        to_status: SubscriptionStatus
    ) -> None:
        """Require transition to be valid or raise ValidationError."""
        if not cls.can_transition_to(from_status, to_status):
            valid_transitions = list(cls.VALID_TRANSITIONS.get(from_status, set()))
            raise ValidationError(
                f"Invalid subscription status transition from {from_status} to {to_status}. "
                f"Valid transitions: {valid_transitions}"
            )
    
    @classmethod
    def is_terminal_status(cls, status: SubscriptionStatus) -> bool:
        """Check if status is terminal """
        return len(cls.VALID_TRANSITIONS.get(status, set())) == 0
