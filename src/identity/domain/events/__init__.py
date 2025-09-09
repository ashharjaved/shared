"""
Domain events for Identity module.

Events represent facts that have occurred in the domain.
They are immutable and carry all necessary data for downstream processing.
"""

from .tenant_events import (
    TenantCreated,
    TenantActivated,
    TenantDeactivated,
    TenantUpdated,
)
from .user_events import (
    UserInvited,
    UserRegistered,
    UserActivated,
    UserDeactivated,
    UserLoggedIn,
    UserLoginFailed,
    UserRolesChanged,
    UserPasswordChanged,
    UserUpdated,
)
from .subscription_events import (
    PlanSubscribed,
    PlanUpgraded,
    PlanDowngraded,
    SubscriptionActivated,
    SubscriptionMarkedPastDue,
    SubscriptionCancelled,
    SubscriptionExpired,
    SubscriptionRenewed,
)

__all__ = [
    # Tenant events
    "TenantCreated",
    "TenantActivated", 
    "TenantDeactivated",
    "TenantUpdated",
    # User events
    "UserInvited",
    "UserRegistered",
    "UserActivated",
    "UserDeactivated", 
    "UserLoggedIn",
    "UserLoginFailed",
    "UserRolesChanged",
    "UserPasswordChanged",
    "UserUpdated",
    # Subscription events
    "PlanSubscribed",
    "PlanUpgraded",
    "PlanDowngraded", 
    "SubscriptionActivated",
    "SubscriptionMarkedPastDue",
    "SubscriptionCancelled",
    "SubscriptionExpired",
    "SubscriptionRenewed",
]