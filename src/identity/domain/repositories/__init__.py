# src/identity/domain/repositories/__init__.py
"""
Domain repository interfaces (ports) for Identity module.

These are pure abstractions defining the contract for data access.
No implementation details - only method signatures and docstrings.
"""

from .tenants import TenantRepository
from .users import UserRepository
from .plans import PlanRepository
from .subscriptions import SubscriptionRepository

__all__ = [
    "TenantRepository",
    "UserRepository", 
    "PlanRepository",
    "SubscriptionRepository",
]