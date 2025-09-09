# src/identity/domain/types.py
"""Domain type definitions and shared types."""

from typing import NewType, Literal
from uuid import UUID
from datetime import datetime

# ID Types
TenantId = NewType('TenantId', UUID)
UserId = NewType('UserId', UUID)
PlanId = NewType('PlanId', UUID)
SubscriptionId = NewType('SubscriptionId', UUID)

# Shared Literals
TenantType = Literal['platform', 'reseller', 'tenant']
SubscriptionStatus = Literal['trial', 'active', 'past_due', 'cancelled', 'expired']

# Type aliases for clarity
Timestamp = datetime
JsonDict = dict[str, object]