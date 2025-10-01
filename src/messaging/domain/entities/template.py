"""WhatsApp message template entity."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
from uuid import UUID
import re


class TemplateStatus(Enum):
    """Template approval status."""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAUSED = "paused"


class TemplateCategory(Enum):
    """Template category as per WhatsApp."""
    MARKETING = "marketing"
    UTILITY = "utility"
    AUTHENTICATION = "authentication"


@dataclass
class TemplateComponent:
    """Template component (header, body, footer, buttons)."""
    type: str  # header, body, footer, buttons
    format: Optional[str] = None  # text, image, video, document
    text: Optional[str] = None
    example: Optional[List[str]] = None  # Example values for variables
    buttons: Optional[List[Dict[str, str]]] = None


@dataclass
class MessageTemplate:
    """WhatsApp message template."""
    id: UUID
    tenant_id: UUID
    channel_id: UUID
    name: str  # Unique template name
    language: str  # e.g., en, es, fr
    category: TemplateCategory
    status: TemplateStatus
    components: List[TemplateComponent]
    whatsapp_template_id: Optional[str] = None  # WhatsApp's ID
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamps."""
        now = datetime.utcnow()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def get_variables(self) -> List[str]:
        """Extract all variables from template components."""
        variables = []
        for component in self.components:
            if component.text:
                # Find {{1}}, {{2}}, etc.
                pattern = r'\{\{(\d+)\}\}'
                matches = re.findall(pattern, component.text)
                variables.extend(matches)
        return sorted(set(variables))
    
    def validate_variables(self, values: Dict[str, str]) -> bool:
        """Validate that all required variables are provided."""
        required = self.get_variables()
        for var in required:
            if var not in values:
                return False
        return True
    
    def can_be_used(self) -> bool:
        """Check if template can be used for sending."""
        return self.status == TemplateStatus.APPROVED
    
    def submit_for_approval(self) -> None:
        """Submit template for WhatsApp approval."""
        if self.status != TemplateStatus.DRAFT:
            raise ValueError("Only draft templates can be submitted")
        self.status = TemplateStatus.PENDING
        self.submitted_at = datetime.utcnow()
        self.updated_at = self.submitted_at
    
    def approve(self, whatsapp_id: str) -> None:
        """Mark template as approved."""
        self.status = TemplateStatus.APPROVED
        self.whatsapp_template_id = whatsapp_id
        self.approved_at = datetime.utcnow()
        self.updated_at = self.approved_at
    
    def reject(self, reason: str) -> None:
        """Mark template as rejected."""
        self.status = TemplateStatus.REJECTED
        self.rejection_reason = reason
        self.updated_at = datetime.utcnow()