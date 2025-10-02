"""
User API Schemas
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class CreateUserRequest(BaseModel):
    """Create user request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 chars)")
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    phone: Optional[str] = Field(None, description="Phone number (E.164 format)")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone format"""
        if v and not v.startswith("+"):
            raise ValueError("Phone must be in E.164 format (e.g., +1234567890)")
        return v


class UpdateUserRequest(BaseModel):
    """Update user request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, description="Phone number (E.164 format)")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone format"""
        if v and not v.startswith("+"):
            raise ValueError("Phone must be in E.164 format")
        return v


class DeactivateUserRequest(BaseModel):
    """Deactivate user request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    reason: Optional[str] = Field(None, max_length=500, description="Deactivation reason")


class UserResponse(BaseModel):
    """User response schema"""
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    
    id: str = Field(..., description="User UUID")
    organization_id: str = Field(..., description="Organization UUID")
    email: str = Field(..., description="User email")
    full_name: str = Field(..., description="User full name")
    phone: Optional[str] = Field(None, description="Phone number")
    is_active: bool = Field(..., description="Account active status")
    email_verified: bool = Field(..., description="Email verification status")
    phone_verified: bool = Field(..., description="Phone verification status")
    last_login_at: Optional[str] = Field(None, description="Last login timestamp (ISO)")
    created_at: str = Field(..., description="Account creation timestamp (ISO)")


class UserListResponse(BaseModel):
    """Paginated user list response"""
    model_config = ConfigDict(extra="forbid")
    
    users: list[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total users matching query")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum records returned")