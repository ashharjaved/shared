"""Message DTOs using Pydantic v2."""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from uuid import UUID
import re


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    to_number: str = Field(..., description="Recipient phone number in E.164 format")
    content: Optional[str] = Field(None, max_length=4096, description="Text message content")
    template_name: Optional[str] = Field(None, max_length=512, description="Template name for template messages")
    template_language: str = Field(default="en", max_length=10, description="Template language code")
    template_variables: Optional[Dict[str, str]] = Field(None, description="Template variables")
    media_url: Optional[str] = Field(None, max_length=2048, description="Media URL for image/video/document messages")
    media_type: Optional[Literal["image", "video", "audio", "document"]] = Field(None, description="Media type")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Idempotency key to prevent duplicates")
    
    @field_validator('to_number')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate E.164 phone format."""
        pattern = r'^\+[1-9]\d{1,14}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid phone number format. Use E.164 format')
        return v
    
    @field_validator('media_url')
    @classmethod
    def validate_media_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate media URL format."""
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('Media URL must be a valid HTTP/HTTPS URL')
        return v
    
    @model_validator(mode='after')
    def validate_content_or_template_or_media(self):
        """Ensure at least one content type is provided."""
        if not any([self.content, self.template_name, self.media_url]):
            raise ValueError('Either content, template_name, or media_url must be provided')
        
        # If template is used, ensure variables are provided if needed
        if self.template_name and not self.content and not self.media_url:
            # Template-only message, variables might be required
            pass
        
        return self


class BulkSendMessageRequest(BaseModel):
    """Request to send messages in bulk."""
    model_config = ConfigDict(extra="forbid")
    
    recipients: List[str] = Field(..., min_length=1, max_length=1000, description="List of recipient phone numbers")
    content: Optional[str] = Field(None, max_length=4096)
    template_name: Optional[str] = Field(None, max_length=512)
    template_language: str = Field(default="en", max_length=10)
    template_variables_list: Optional[List[Dict[str, str]]] = Field(None, description="List of variables per recipient")
    
    @field_validator('recipients')
    @classmethod
    def validate_recipients(cls, v: List[str]) -> List[str]:
        """Validate all recipient phone numbers."""
        pattern = r'^\+[1-9]\d{1,14}$'
        for phone in v:
            if not re.match(pattern, phone):
                raise ValueError(f'Invalid phone number format: {phone}')
        return v


class MessageResponse(BaseModel):
    """Message response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    channel_id: UUID
    direction: str
    message_type: str
    from_number: str
    to_number: str
    content: Optional[str]
    media_url: Optional[str]
    status: str
    whatsapp_message_id: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]


class MessageListResponse(BaseModel):
    """List of messages."""
    messages: List[MessageResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class MessageStatusUpdate(BaseModel):
    """Message status update."""
    message_id: UUID
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: datetime
    error: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    """Conversation thread response."""
    phone_number: str
    messages: List[MessageResponse]
    last_message_at: datetime
    total_messages: int
    unread_count: int = 0