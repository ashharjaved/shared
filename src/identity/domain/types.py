# src/identity/domain/types.py
"""Domain type definitions and shared types."""

from enum import Enum
from typing import NewType, Literal
from uuid import UUID
from datetime import datetime

# ID Types
TenantId = NewType('TenantId', UUID)
UserId = NewType('UserId', UUID)
PlanId = NewType('PlanId', UUID)
SubscriptionId = NewType('SubscriptionId', UUID)

# Shared Literals
TenantType = Literal['PLATFORM', 'RESELLER', 'TENANT']

# Type aliases for clarity
Timestamp = datetime
JsonDict = dict[str, object]

class SubscriptionStatus(Enum):
    ACTIVE = "ACTIVE"
    TRIAL = "TRIAL"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    PAST_DUE = "PAST_DUE"