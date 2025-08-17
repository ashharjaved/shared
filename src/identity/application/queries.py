from __future__ import annotations
from dataclasses import dataclass

@dataclass
class GetTenant:
    tenant_id: str

@dataclass
class GetUser:
    tenant_id: str
    user_id: str
