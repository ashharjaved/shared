"""Channel DTOs using Pydantic v2."""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import re


class ChannelCreateRequest(BaseModel):
    """Request to create a channel."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    name: str = Field(..., min_length=1, max_length=255, description="Channel name")
    phone_number_id: str = Field(..., min_length=1, max_length=255, description="WhatsApp Phone Number ID")
    business_phone: str = Field(..., description="Business phone number in E.164 format")
    access_token: str = Field(..., min_length=10, description="WhatsApp API access token")
    rate_limit_per_second: int = Field(default=80, ge=1, le=1000, description="Messages per second limit")
    monthly_message_limit: Optional[int] = Field(default=None, ge=0, description="Monthly message quota")
    
    @field_validator('business_phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate E.164 phone format."""
        pattern = r'^\+[1-9]\d{1,14}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid phone number format. Use E.164 format (e.g., +1234567890)')
        return v
    
    @field_validator('access_token')
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Basic token validation."""
        if len(v.strip()) < 10:
            raise ValueError('Access token too short')
        return v


class ChannelUpdateRequest(BaseModel):
    """Request to update a channel."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    access_token: Optional[str] = Field(None, min_length=10)
    rate_limit_per_second: Optional[int] = Field(None, ge=1, le=1000)
    monthly_message_limit: Optional[int] = Field(None, ge=0)
    
    @model_validator(mode='after')
    def check_at_least_one_field(self):
        """Ensure at least one field is provided for update."""
        if not any([self.name, self.access_token, self.rate_limit_per_second, 
                   self.monthly_message_limit is not None]):
            raise ValueError('At least one field must be provided for update')
        return self


class ChannelResponse(BaseModel):
    """Channel response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    tenant_id: UUID
    name: str
    phone_number_id: str
    business_phone: str
    status: str
    rate_limit_per_second: int
    monthly_message_limit: Optional[int]
    current_month_usage: int
    webhook_url: Optional[str] = None
    webhook_verify_token: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator('webhook_url', mode='before')
    @classmethod
    def build_webhook_url(cls, v, info):
        """Build webhook URL from channel ID."""
        if not v and info.data and 'id' in info.data:
            # Build webhook URL from channel ID
            base_url = "https://api.example.com"  # Should come from config
            return f"{base_url}/webhooks/whatsapp/{info.data['id']}"
        return v


class ChannelListResponse(BaseModel):
    """List of channels."""
    channels: List[ChannelResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class ChannelStatsResponse(BaseModel):
    """Channel statistics."""
    channel_id: UUID
    messages_sent_today: int
    messages_received_today: int
    messages_failed_today: int
    current_month_usage: int
    monthly_limit: Optional[int]
    usage_percentage: Optional[float]
    last_message_at: Optional[datetime]