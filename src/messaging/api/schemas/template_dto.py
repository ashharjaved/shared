"""Template DTOs using Pydantic v2."""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID
import re


class TemplateComponentRequest(BaseModel):
    """Template component request."""
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["header", "body", "footer", "buttons"] = Field(..., description="Component type")
    format: Optional[Literal["text", "image", "video", "document"]] = Field(None, description="Header format")
    text: Optional[str] = Field(None, max_length=1024, description="Component text")
    example: Optional[List[str]] = Field(None, description="Example values for variables")
    buttons: Optional[List[Dict[str, str]]] = Field(None, max_length=3, description="Button definitions")
    
    @model_validator(mode='after')
    def validate_component(self):
        """Validate component based on type."""
        if self.type in ["header", "body", "footer"] and not self.text:
            raise ValueError(f"{self.type} component must have text")
        if self.type == "buttons" and not self.buttons:
            raise ValueError("Buttons component must have buttons defined")
        return self


class TemplateCreateRequest(BaseModel):
    """Request to create a template."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    name: str = Field(..., min_length=1, max_length=512, description="Template name")
    language: str = Field(..., min_length=2, max_length=10, description="Language code (e.g., en, es)")
    category: Literal["marketing", "utility", "authentication"] = Field(..., description="Template category")
    components: List[TemplateComponentRequest] = Field(..., min_length=1, max_length=4, description="Template components")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate template name format."""
        # WhatsApp template names: lowercase, underscores only
        pattern = r'^[a-z][a-z0-9_]*$'
        if not re.match(pattern, v):
            raise ValueError('Template name must be lowercase with underscores only')
        return v
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate language code."""
        valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'hi', 'zh', 'ar']
        if v not in valid_languages:
            raise ValueError(f'Language must be one of: {", ".join(valid_languages)}')
        return v


class TemplateUpdateRequest(BaseModel):
    """Request to update a template."""
    model_config = ConfigDict(extra="forbid")
    
    components: Optional[List[TemplateComponentRequest]] = Field(None, min_length=1, max_length=4)
    category: Optional[Literal["marketing", "utility", "authentication"]] = Field(None)
    
    @model_validator(mode='after')
    def check_at_least_one_field(self):
        """Ensure at least one field is provided."""
        if not any([self.components, self.category]):
            raise ValueError('At least one field must be provided for update')
        return self


class TemplateResponse(BaseModel):
    """Template response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    tenant_id: UUID
    channel_id: UUID
    name: str
    language: str
    category: str
    status: str
    components: List[Dict[str, Any]]
    whatsapp_template_id: Optional[str]
    rejection_reason: Optional[str]
    variables_count: int = 0
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    
    @field_validator('variables_count', mode='before')
    @classmethod
    def count_variables(cls, v, info):
        """Count template variables."""
        if 'components' in info.data:
            count = 0
            for comp in info.data['components']:
                if isinstance(comp, dict) and 'text' in comp:
                    import re
                    matches = re.findall(r'\{\{(\d+)\}\}', comp.get('text', ''))
                    count += len(matches)
            return count
        return v


class TemplateListResponse(BaseModel):
    """List of templates."""
    templates: List[TemplateResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class TemplateSubmitRequest(BaseModel):
    """Request to submit template for approval."""
    model_config = ConfigDict(extra="forbid")
    
    business_id: str = Field(..., description="WhatsApp Business ID")


class TemplateTestRequest(BaseModel):
    """Request to test a template."""
    model_config = ConfigDict(extra="forbid")
    
    to_number: str = Field(..., description="Test recipient phone number")
    variables: Optional[Dict[str, str]] = Field(None, description="Test variables")
    
    @field_validator('to_number')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number."""
        pattern = r'^\+[1-9]\d{1,14}$'
        if not re.match(pattern, v):
            raise ValueError('Invalid phone number format')
        return v