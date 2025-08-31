from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class ConfigReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    key: str
    value: Dict[str, Any]
    is_encrypted: bool
    config_type: str
    source: str


class ConfigUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_.:-]{1,100}$")
    value: Dict[str, Any]
    is_encrypted: bool = False
    config_type: str = Field(default="GENERAL")


class ConfigDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deleted: bool


class RateLimitCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    per_second: int = Field(ge=1, le=10_000)
    enable_global: bool = True
    enable_monthly: bool = False
    monthly_quota: Optional[int] = Field(default=None, ge=1)


class RateLimitDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    allowed: bool
    remaining_in_window: Optional[int] = None
    reason: Optional[str] = None
