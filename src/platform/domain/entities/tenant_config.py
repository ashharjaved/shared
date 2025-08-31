from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from ..value_objects.config_key import ConfigKey


class ConfigType(str, Enum):
    """Enumeration that mirrors the DB enum `config_type_enum`."""
    GENERAL = "GENERAL"
    SECURITY = "SECURITY"
    BILLING = "BILLING"


@dataclass(frozen=True, slots=True)
class TenantConfiguration:
    """
    Pure domain entity for a tenant-scoped configuration key/value.

    Notes:
    - `value` is the canonical Python representation of `config_value` JSONB.
    - If `is_encrypted=True`, `value` MUST represent an envelope-encrypted blob
      as produced by the infrastructure crypto service (opaque to the domain).
    - Secrets are **never** automatically decrypted in the domain layer.
    """
    id: UUID
    tenant_id: UUID
    key: ConfigKey
    value: Dict[str, Any]
    config_type: ConfigType
    is_encrypted: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    def is_soft_deleted(self) -> bool:
        return self.deleted_at is not None
