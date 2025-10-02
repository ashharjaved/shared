"""
Message Template Entity
Represents WhatsApp-approved message templates.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from shared.domain.base_entity import BaseEntity


class MessageTemplate(BaseEntity):
    """
    Entity for WhatsApp message templates.
    
    Attributes:
        tenant_id: Owning tenant
        name: Template name (unique per tenant + language)
        language: Template language code (en, hi, etc.)
        category: utility, marketing, authentication
        status: draft, pending, approved, rejected, deprecated
        body_text: Template body with {{N}} variables
        header_text: Optional header
        footer_text: Optional footer
        buttons: Interactive buttons configuration
        variables: List of variable names
        rejection_reason: Reason if rejected by WhatsApp
        wa_template_id: WhatsApp template ID (after approval)
        approved_at: Approval timestamp
    """
    
    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        name: str,
        language: str,
        category: str,
        body_text: str,
        status: str = "draft",
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        buttons: Optional[List[dict]] = None,
        variables: Optional[List[str]] = None,
        rejection_reason: Optional[str] = None,
        wa_template_id: Optional[str] = None,
        approved_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        super().__init__(id, created_at, updated_at)
        self.tenant_id = tenant_id
        self.name = name
        self.language = language
        self.category = category
        self.body_text = body_text
        self.status = status
        self.header_text = header_text
        self.footer_text = footer_text
        self.buttons = buttons or []
        self.variables = variables or []
        self.rejection_reason = rejection_reason
        self.wa_template_id = wa_template_id
        self.approved_at = approved_at
    
    def submit_for_approval(self) -> None:
        """Submit template to WhatsApp for approval."""
        if self.status != "draft":
            raise ValueError("Only draft templates can be submitted")
        self.status = "pending"
    
    def approve(self, wa_template_id: str) -> None:
        """Mark template as approved by WhatsApp."""
        self.status = "approved"
        self.wa_template_id = wa_template_id
        self.approved_at = datetime.utcnow()
    
    def reject(self, reason: str) -> None:
        """Mark template as rejected with reason."""
        self.status = "rejected"
        self.rejection_reason = reason
    
    def deprecate(self) -> None:
        """Deprecate an approved template."""
        self.status = "deprecated"
    
    def is_usable(self) -> bool:
        """Check if template can be used for sending."""
        return self.status == "approved"
    
    def __repr__(self) -> str:
        return f"<MessageTemplate(id={self.id}, name={self.name}, status={self.status})>"