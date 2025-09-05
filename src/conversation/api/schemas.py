#*** Begin: src/conversation/api/schemas.py ***
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

# Reuse strict JSON typing from domain (no Any)
from pydantic import JsonValue as JSONValue

# -----------------------
# Flow DTOs
# -----------------------
class MenuFlowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    industry_type: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    is_active: bool = True
    is_default: bool = False
    # The JSON should match MenuDefinition schema: {"menus": {...}}
    definition: Dict[str, JSONValue] = Field(..., alias="definition_json")

class MenuFlowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    industry_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    version: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    definition: Optional[Dict[str, JSONValue]] = Field(default=None, alias="definition_json")

class MenuFlowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    name: str
    industry_type: str
    version: int
    is_active: bool
    is_default: bool
    definition: Dict[str, JSONValue] = Field(..., alias="definition_json")
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# -----------------------
# Session DTOs (debug)
# -----------------------
class SessionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    channel_id: UUID
    phone_number: str
    current_menu_id: Optional[UUID] = None
    status: str
    last_activity: datetime
    expires_at: datetime
    message_count: int

MenuFlowCreate.model_rebuild()
MenuFlowUpdate.model_rebuild()
MenuFlowRead.model_rebuild()
SessionRead.model_rebuild()
#*** End: src/conversation/api/schemas.py ***
