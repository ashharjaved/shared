"""
Organization API Schemas
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class CreateOrganizationRequest(BaseModel):
    """Create organization request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-safe slug")
    industry: str = Field(..., description="Industry: healthcare, education, retail, other")
    timezone: str = Field(default="UTC", description="Timezone (e.g., America/New_York)")
    language: str = Field(default="en", description="Primary language code (e.g., en, es)")
    
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format"""
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        return v


class UpdateOrganizationRequest(BaseModel):
    """Update organization request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    timezone: Optional[str] = Field(None)
    language: Optional[str] = Field(None)


class OrganizationResponse(BaseModel):
    """Organization response schema"""
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    
    id: str = Field(..., description="Organization UUID")
    name: str = Field(..., description="Organization name")
    slug: str = Field(..., description="URL-safe slug")
    industry: str = Field(..., description="Industry vertical")
    is_active: bool = Field(..., description="Active status")
    timezone: str = Field(..., description="Timezone")
    language: str = Field(..., description="Primary language")
    created_at: str = Field(..., description="Creation timestamp (ISO)")