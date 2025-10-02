"""
Authentication API Schemas
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    """Login request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class LoginResponse(BaseModel):
    """Login response schema"""
    model_config = ConfigDict(extra="forbid")
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")
    user_id: str = Field(..., description="User UUID")
    organization_id: str = Field(..., description="Organization UUID")
    email: str = Field(..., description="User email")
    roles: list[str] = Field(default_factory=list, description="User roles")


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(BaseModel):
    """Refresh token response schema (same as login)"""
    model_config = ConfigDict(extra="forbid")
    
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    organization_id: str
    email: str
    roles: list[str] = Field(default_factory=list)


class PasswordResetRequest(BaseModel):
    """Password reset request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    email: EmailStr = Field(..., description="User email address")


class PasswordResetConfirmRequest(BaseModel):
    """Password reset confirmation schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    reset_token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class EmailVerificationRequest(BaseModel):
    """Email verification request schema"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    verification_token: str = Field(..., description="Email verification token")


class PasswordResetResponse(BaseModel):
    """Generic success response"""
    model_config = ConfigDict(extra="forbid")
    
    message: str = Field(..., description="Success message")


class EmailVerificationResponse(BaseModel):
    """Email verification response"""
    model_config = ConfigDict(extra="forbid")
    
    message: str = Field(..., description="Success message")
    email_verified: bool = Field(..., description="Email verification status")