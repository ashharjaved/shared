from __future__ import annotations
# src/platform/domain/entities.py

from datetime import datetime
from typing import Any, Optional, Literal

from pydantic import BaseModel, Field
from uuid import UUID
from .value_objects import ConfigType,ConfigSourceLevel

class TenantConfig(BaseModel):
    id: UUID
    tenant_id: UUID
    config_key: str
    config_value: Any
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class TenantConfigView(BaseModel):
    """
    Redacted view for API/consumers. If is_encrypted=True, config_value MUST be None.
    """
    config_key: str
    config_value: Optional[Any] = None
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False
    source_level: ConfigSourceLevel = Field(default=ConfigSourceLevel.CLIENT)
    updated_at: Optional[datetime] = None


class SetConfigDTO(BaseModel):
    tenant_id: UUID
    config_key: str
    config_value: Any
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False


class DeleteConfigDTO(BaseModel):
    tenant_id: UUID
    config_key: str


class ResolvedConfigDTO(BaseModel):
    """
    Output of hierarchy resolution for cache/internal use (not directly API).
    Value is present even if encrypted; caller must redact for API.
    """
    config_key: str
    config_value: Any
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False
    source_level: ConfigSourceLevel = ConfigSourceLevel.CLIENT
    updated_at: Optional[datetime] = None