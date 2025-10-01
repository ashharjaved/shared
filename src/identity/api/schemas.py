# src/identity/api/schemas.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict, AliasChoices



# ===== Password Reset Schemas =====


# ===== User Management Schemas =====

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


# ===== Authentication Schemas =====

class LoginRequest(BaseModel):
    """Login request payload."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    tenant_id: str = Field(..., description="Tenant context for authentication")
    
    model_config = {"str_strip_whitespace": True}


class RefreshRequest(BaseModel):
    """Token refresh request payload."""
    
    refresh_token: str = Field(..., description="Valid refresh token")


class LoginResponse(BaseModel):
    """Login/refresh response with tokens and user info."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: Optional[dict] = Field(None, description="User profile information")


# ===== Password Reset Schemas =====

class PasswordResetRequest(BaseModel):
    """Password reset initiation request."""
    
    email: EmailStr = Field(..., description="User email address")
    tenant_id: str = Field(..., description="Tenant context")
    
    model_config = {"str_strip_whitespace": True}


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation with new password."""
    
    token: str = Field(..., min_length=16, description="Reset token from email")
    email: EmailStr = Field(..., description="User email address")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (min 8 chars, must include uppercase, lowercase, number, special char)"
    )
    tenant_id: str = Field(..., description="Tenant context")
    
    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in v):
            raise ValueError("Password must contain at least one special character")
        
        return v
    
    model_config = {"str_strip_whitespace": True}


# ===== User Management Schemas =====

class UserCreate(BaseModel):
    """Create new user request."""
    
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    password: str = Field(..., min_length=8, description="User password")
    role: str = Field(..., description="User role (TENANT_ADMIN, STAFF, etc.)")
    tenant_id: str = Field(..., description="Tenant ID")
    phone: Optional[str] = Field(None, description="Phone number")
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
    
    model_config = {"str_strip_whitespace": True}


class UserRead(BaseModel):
    """User profile response."""
    
    id: str = Field(..., description="User ID (UUID)")
    email: str = Field(..., description="Email address")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    role: str = Field(..., description="User role")
    tenant_id: str = Field(..., description="Tenant ID")
    phone: Optional[str] = Field(None, description="Phone number")
    is_active: bool = Field(..., description="Account status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Update user profile request."""
    
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None)
    
    model_config = {"str_strip_whitespace": True}


class UserStatusUpdate(BaseModel):
    """Update user active status."""
    
    is_active: bool = Field(..., description="Account active status")


class UserRoleUpdate(BaseModel):
    """Update user role."""
    
    role: str = Field(..., description="New role")


# ===== Tenant Management Schemas =====

class TenantCreate(BaseModel):
    """Create tenant request."""
    
    name: str = Field(..., min_length=1, max_length=200, description="Tenant organization name")
    tenant_type: str = Field(..., description="PLATFORM_OWNER, RESELLER, or CLIENT")
    parent_tenant_id: Optional[str] = Field(None, description="Parent tenant ID (for hierarchy)")
    plan: Optional[str] = Field(None, description="Subscription plan")
    
    model_config = {"str_strip_whitespace": True}


class TenantRead(BaseModel):
    """Tenant profile response."""
    
    id: str = Field(..., description="Tenant ID (UUID)")
    name: str = Field(..., description="Organization name")
    slug: str = Field(..., description="URL-friendly slug")
    tenant_type: str = Field(..., description="Tenant type")
    parent_tenant_id: Optional[str] = Field(None, description="Parent tenant ID")
    plan: Optional[str] = Field(None, description="Subscription plan")
    is_active: bool = Field(..., description="Tenant status")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {"from_attributes": True}


class TenantStatusUpdate(BaseModel):
    """Update tenant status."""
    
    is_active: bool = Field(..., description="Active status")


# ===== Error Response Schema =====

class ErrorResponse(BaseModel):
    """Standardized error response."""
    
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error context")
    
    model_config = {"json_schema_extra": {
        "example": {
            "code": "auth.invalid_credentials",
            "message": "Invalid credentials",
            "details": None
        }
    }}