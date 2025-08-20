from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

@dataclass
class GetTenant:
    tenant_id: UUID

@dataclass
class GetUser:
    tenant_id: UUID
    user_id: str
