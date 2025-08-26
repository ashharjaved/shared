from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ConfigCreated:
    tenant_id: UUID
    key: str
    created_at: datetime


@dataclass(frozen=True)
class ConfigUpdated:
    tenant_id: UUID
    key: str
    updated_at: datetime


@dataclass(frozen=True)
class ConfigDeleted:
    tenant_id: UUID
    key: str
    deleted_at: datetime
