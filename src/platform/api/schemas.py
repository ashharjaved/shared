from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, List
from pydantic import BaseModel, Field
from uuid import UUID

from ..domain.entities import ConfigType


# ---------- Requests ----------

class SetConfigRequest(BaseModel):
    config_key: str = Field(min_length=1, max_length=100)
    config_value: Any
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False


# ---------- Responses (Error Contract compatible) ----------

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ConfigResponse(BaseModel):
    config_key: str
    config_value: Optional[Any] = None
    config_type: ConfigType = ConfigType.GENERAL
    is_encrypted: bool = False
    source_level: str
    updated_at: Optional[datetime] = None


class ListConfigsResponse(BaseModel):
    items: List[ConfigResponse]
