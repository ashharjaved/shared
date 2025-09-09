# src/identity/domain/entities/subscription.py
"""Tenant plan subscription entity."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ..types import SubscriptionId, TenantId, PlanId, SubscriptionStatus, JsonDict
from ..value_objects import Timestamps
from ..errors import InvariantViolation, ValidationError


@dataclass(slots=True)
class TenantPlanSubscription:
    """Tenant subscription to a plan."""
    
    id: SubscriptionId
    tenant_id: TenantId
    plan_id: PlanId
    status: SubscriptionStatus
    start_at: datetime
    end_at: datetime | None
    meta_json: JsonDict
    timestamps: Timestamps
    
    def __post_init__(self) -> None:
        """Validate subscription invariants."""
        if self.end_at and self.start_at >= self.end_at:
            raise ValidationError("Subscription start_at must be before end_at")
    
    @classmethod
    def create_trial(
        cls,
        tenant_id: TenantId,
        plan_id: PlanId,
        trial_days: int = 14,
        meta: dict[str, object] | None = None,
    ) -> 'TenantPlanSubscription':
        """Create trial subscription."""
        start = datetime.now(timezone.utc)
        end = start.replace(day=start.day + trial_days) if trial_days > 0 else None
        
        return cls(
            id=SubscriptionId(uuid4()),
            tenant_id=tenant_id,
            plan_id=plan_id,
            status='trial',
            start_at=start,
            end_at=end,
            meta_json=meta or {},
            timestamps=Timestamps.now(),
        )
    
    @classmethod
    def create_active(
        cls,
        tenant_id: TenantId,
        plan_id: PlanId,
        end_at: datetime | None = None,
        meta: dict[str, object] | None = None,
    ) -> 'TenantPlanSubscription':
        """Create active subscription."""
        return cls(
            id=SubscriptionId(uuid4()),
            tenant_id=tenant_id,
            plan_id=plan_id,
            status='active',
            start_at=datetime.now(timezone.utc),
            end_at=end_at,
            meta_json=meta or {},
            timestamps=Timestamps.now(),
        )
    
    def activate(self) -> None:
        """Activate subscription."""
        if self.status == 'cancelled':
            raise InvariantViolation("Cannot activate cancelled subscription")
        
        if self.status == 'expired':
            raise InvariantViolation("Cannot activate expired subscription")
        
        self.status = 'active'
        self._update_timestamp()
    
    def mark_past_due(self) -> None:
        """Mark subscription as past due."""
        if self.status not in {'active', 'trial'}:
            raise InvariantViolation(f"Cannot mark {self.status} subscription as past due")
        
        self.status = 'past_due'
        self._update_timestamp()
    
    def cancel(self) -> None:
        """Cancel subscription."""
        if self.status in {'cancelled', 'expired'}:
            return  # Already terminal state
        
        self.status = 'cancelled'
        self._update_timestamp()
    
    def expire(self) -> None:
        """Expire subscription."""
        if self.status == 'cancelled':
            return  # Keep cancelled state
        
        self.status = 'expired'
        self._update_timestamp()
    
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        if self.status not in {'active', 'trial'}:
            return False
        
        if self.end_at and datetime.now(timezone.utc) > self.end_at:
            return False
        
        return True
    
    def is_terminal(self) -> bool:
        """Check if subscription is in terminal state."""
        return self.status in {'cancelled', 'expired'}
    
    def days_remaining(self) -> int | None:
        """Get days remaining in subscription."""
        if not self.end_at:
            return None
        
        remaining = self.end_at - datetime.now(timezone.utc)
        return max(0, remaining.days)
    
    def _update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.timestamps = self.timestamps.update_timestamp()
