from __future__ import annotations

from pydantic import BaseModel
from uuid import UUID
from typing import Any

from platform.domain.value_objects import ConfigSourceLevel

from ..domain.entities import ConfigType


class SetConfigCommand(BaseModel):
    tenant_id: UUID
    config_key: str
    config_value: Any
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False

# In your SetConfigDTO definition, make sure it has:
class SetConfigDTO(BaseModel):
    config_key: str
    config_value: Any
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False
    source_level: ConfigSourceLevel = ConfigSourceLevel.CLIENT
    tenant_id: UUID  # This is required for cache operations

class DeleteConfigCommand(BaseModel):
    tenant_id: UUID
    config_key: str
