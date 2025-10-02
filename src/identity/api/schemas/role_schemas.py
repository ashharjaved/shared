"""
Role API Schemas
"""
from __future__ import annotations
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class AssignRoleRequest(BaseModel):
    """Assign role request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    user_id: str = Field(..., description="User UUID")
    role_id: str = Field(..., description="Role UUID")


class RevokeRoleRequest(BaseModel):
    """Revoke role request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    user_id: str = Field(..., description="User UUID")
    role_id: str = Field(..., description="Role UUID")


class RoleResponse(BaseModel):
    """Role response schema"""
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    
    id: str = Field(..., description="Role UUID")
    organization_id: str = Field(..., description="Organization UUID")
    name: str = Field(..., description="Role name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: list[str] = Field(..., description="List of permissions")
    is_system: bool = Field(..., description="System role flag")
    created_at: str = Field(..., description="Creation timestamp (ISO)")


class UserRolesResponse(BaseModel):
    """User roles response schema"""
    model_config = ConfigDict(extra="forbid")
    
    user_id: str = Field(..., description="User UUID")
    roles: list[RoleResponse] = Field(..., description="List of assigned roles")