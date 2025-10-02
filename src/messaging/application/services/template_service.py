"""
Template Service
Business logic for message template management.
"""
from typing import List, Optional
from uuid import UUID, uuid4

from src.messaging.domain.entities.message_template import MessageTemplate
from src.messaging.domain.protocols.template_repository import TemplateRepository
from src.messaging.domain.protocols.whatsapp_gateway_repository import WhatsAppGateway
from src.messaging.domain.exceptions import TemplateNotFoundError, TemplateNotApprovedError
from shared.infrastructure.observability.logger import get_logger
from shared.infrastructure.security.audit_log import AuditLogger

logger = get_logger(__name__)


class TemplateService:
    """
    Application service for template operations.
    
    Handles template lifecycle: creation, submission, approval tracking.
    """
    
    def __init__(
        self,
        template_repo: TemplateRepository,
        whatsapp_gateway: WhatsAppGateway,
        audit_logger: AuditLogger
    ):
        self.template_repo = template_repo
        self.whatsapp_gateway = whatsapp_gateway
        self.audit_logger = audit_logger
    
    async def create_template(
        self,
        tenant_id: UUID,
        name: str,
        language: str,
        category: str,
        body_text: str,
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        buttons: Optional[List[dict]] = None,
        variables: Optional[List[str]] = None,
        user_id: Optional[UUID] = None
    ) -> MessageTemplate:
        """Create new message template in draft status."""
        # Check for duplicate
        existing = await self.template_repo.get_by_name_and_language(
            tenant_id, name, language
        )
        if existing:
            raise ValueError("Template with this name and language already exists")
        
        # Create entity
        template = MessageTemplate(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            language=language,
            category=category,
            body_text=body_text,
            header_text=header_text,
            footer_text=footer_text,
            buttons=buttons or [],
            variables=variables or []
        )
        
        # Persist
        template = await self.template_repo.create(template)
        
        # Audit log
        self.audit_logger.log_data_access(
            organization_id=tenant_id,
            user_id=UUID(user_id) if user_id else None,
            action="template.created",
            resource_type="template",
            resource_id=template.id,
#            details={"name": name, "language": language}
        )
        
        logger.info(f"Template created: {template.id}")
        
        return template
    
    async def submit_for_approval(
        self,
        template_id: UUID,
        waba_id: str,
        user_id: Optional[UUID] = None
    ) -> MessageTemplate:
        """Submit template to WhatsApp for approval."""
        template = await self.template_repo.get_by_id(template_id)
        
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # Submit to WhatsApp
        wa_template = {
            "name": template.name,
            "language": template.language,
            "category": template.category,
            "components": self._build_components(template)
        }
        
        response = await self.whatsapp_gateway.create_template(waba_id, wa_template)
        
        # Update status
        template.submit_for_approval()
        template = await self.template_repo.update(template)
        
        # Audit log
        self.audit_logger.log_data_access(
            organization_id=template.tenant_id,
            user_id=user_id,
            action="template.submitted",
            resource_type="template",
            resource_id=template.id,
        )
        
        logger.info(f"Template submitted: {template.id}")
        
        return template
    
    async def mark_approved(
        self,
        template_id: UUID,
        wa_template_id: str,
        user_id: Optional[UUID] = None
    ) -> MessageTemplate:
        """Mark template as approved by WhatsApp."""
        template = await self.template_repo.get_by_id(template_id)
        
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        template.approve(wa_template_id)
        template = await self.template_repo.update(template)
        
        await self.audit_logger.log(
            tenant_id=template.tenant_id,
            user_id=user_id,
            action="template.approved",
            resource_type="template",
            resource_id=template.id
        )
        
        logger.info(f"Template approved: {template.id}")
        
        return template
    
    async def mark_rejected(
        self,
        template_id: UUID,
        reason: str,
        user_id: Optional[UUID] = None
    ) -> MessageTemplate:
        """Mark template as rejected by WhatsApp."""
        template = await self.template_repo.get_by_id(template_id)
        
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        template.reject(reason)
        template = await self.template_repo.update(template)
        
        await self.audit_logger.log(
            tenant_id=template.tenant_id,
            user_id=user_id,
            action="template.rejected",
            resource_type="template",
            resource_id=template.id,
            details={"reason": reason}
        )
        
        logger.warning(f"Template rejected: {template.id}, reason: {reason}")
        
        return template
    
    async def list_templates(
        self,
        tenant_id: UUID,
        status: Optional[str] = None
    ) -> List[MessageTemplate]:
        """List templates for tenant."""
        return await self.template_repo.list_by_tenant(tenant_id, status)
    
    async def get_template(self, template_id: UUID) -> MessageTemplate:
        """Get template by ID."""
        template = await self.template_repo.get_by_id(template_id)
        
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        return template
    
    def _build_components(self, template: MessageTemplate) -> List[dict]:
        """Build WhatsApp template components from domain template."""
        components = []
        
        # Header
        if template.header_text:
            components.append({
                "type": "HEADER",
                "format": "TEXT",
                "text": template.header_text
            })
        
        # Body
        components.append({
            "type": "BODY",
            "text": template.body_text
        })
        
        # Footer
        if template.footer_text:
            components.append({
                "type": "FOOTER",
                "text": template.footer_text
            })
        
        # Buttons
        if template.buttons:
            components.append({
                "type": "BUTTONS",
                "buttons": template.buttons
            })
        
        return components