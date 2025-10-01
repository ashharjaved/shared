# src/identity/domain/services/subscription_rules.py
"""Subscription lifecycle rules domain service."""

from ..types import SubscriptionStatus
from ..exception import ValidationError

class SubscriptionRules:
    """Business rules for subscription lifecycle transitions."""
    
    # Valid state transitions
    VALID_TRANSITIONS: dict[SubscriptionStatus, set[SubscriptionStatus]] = {
    SubscriptionStatus.TRIAL: {SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED},
    SubscriptionStatus.ACTIVE: {SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED},
    SubscriptionStatus.PAST_DUE: {SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED},
    SubscriptionStatus.CANCELLED: set(),
    SubscriptionStatus.EXPIRED: set(),
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
