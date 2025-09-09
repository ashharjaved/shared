from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from identity.domain.types import PlanId, SubscriptionId, UserId

from ._base import EventBase


@dataclass(frozen=True, slots=True)
class PlanSubscribed(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    plan_id: PlanId = PlanId(uuid4())
    plan_slug: str = field(default="")
    actor_id: Optional[UserId] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class PlanUpgraded(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    from_plan_id: PlanId = PlanId(uuid4())
    from_plan_slug: str = field(default="")
    to_plan_id: PlanId = PlanId(uuid4())
    to_plan_slug: str = field(default="")
    actor_id: Optional[UserId] = None
    effective_at: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class PlanDowngraded(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    from_plan_id: PlanId = PlanId(uuid4())
    from_plan_slug: str = field(default="")
    to_plan_id: PlanId = PlanId(uuid4())
    to_plan_slug: str = field(default="")
    actor_id: Optional[UserId] = None
    effective_at: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class SubscriptionActivated(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    reason: Optional[str] = None  # e.g., "trial_started" | "payment_confirmed"


@dataclass(frozen=True, slots=True)
class SubscriptionMarkedPastDue(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    reason: Optional[str] = None          # e.g., "payment_failed"
    as_of: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class SubscriptionCancelled(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    actor_id: Optional[UserId] = None
    reason: Optional[str] = None
    effective_at: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class SubscriptionExpired(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    expired_at: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class SubscriptionRenewed(EventBase):
    subscription_id: SubscriptionId = SubscriptionId(uuid4())
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    mode: str = field(default="auto")  # "auto" | "manual"
