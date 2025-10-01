"""Template management service."""

from datetime import datetime
import logging
from typing import List, Optional, Dict, Any
import uuid

from src.messaging.domain.entities.template import (
    MessageTemplate, TemplateStatus, TemplateCategory, TemplateComponent
)
from src.messaging.domain.interfaces.repositories import TemplateRepository, ChannelRepository
from src.messaging.domain.interfaces.external_services import WhatsAppClient
from src.messaging.domain.events.message_events import TemplateApproved
from src.shared.infrastructure.events import EventBus

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing WhatsApp message templates."""
    
    def __init__(
        self,
        template_repo: TemplateRepository,
        channel_repo: ChannelRepository,
        whatsapp_client: WhatsAppClient,
        event_bus: EventBus
    ):
        self.template_repo = template_repo
        self.channel_repo = channel_repo
        self.whatsapp_client = whatsapp_client
        self.event_bus = event_bus
    
    async def create_template(
        self,
        tenant_id: uuid.UUID,
        channel_id: uuid.UUID,
        name: str,
        language: str,
        category: str,
        components: List[Dict[str, Any]]
    ) -> MessageTemplate:
        """Create a new message template."""
        try:
            # Validate channel exists
            channel = await self.channel_repo.get_by_id(channel_id, tenant_id)
            if not channel:
                raise ValueError(f"Channel {channel_id} not found")
            
            # Parse components
            template_components = []
            for comp in components:
                template_components.append(TemplateComponent(
                    type=comp["type"],
                    format=comp.get("format"),
                    text=comp.get("text"),
                    example=comp.get("example"),
                    buttons=comp.get("buttons")
                ))
            
            # Create template entity
            template = MessageTemplate(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                channel_id=channel_id,
                name=name,
                language=language,
                category=TemplateCategory(category),
                status=TemplateStatus.DRAFT,
                components=template_components
            )
            
            # Save template
            template = await self.template_repo.create(template)
            
            logger.info(f"Template {template.id} created: {name}")
            
            return template
            
        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            raise
    
    async def submit_for_approval(
        self,
        template_id: uuid.UUID,
        tenant_id: uuid.UUID,
        business_id: str
    ) -> MessageTemplate:
        """Submit template to WhatsApp for approval."""
        try:
            # Get template
            template = await self.template_repo.get_by_id(template_id, tenant_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            # Get channel for access token
            channel = await self.channel_repo.get_by_id(template.channel_id, tenant_id)
            if not channel:
                raise ValueError(f"Channel {template.channel_id} not found")
            
            # Build WhatsApp template data
            wa_template_data = self._build_whatsapp_template(template)
            
            # Submit to WhatsApp
            response = await self.whatsapp_client.submit_template(
                business_id,
                channel.access_token,
                wa_template_data
            )
            
            if "id" in response:
                # Mark as pending
                template.submit_for_approval()
                template.whatsapp_template_id = response["id"]
                await self.template_repo.update(template)
                
                logger.info(f"Template {template_id} submitted for approval")
            else:
                error = response.get("error", {}).get("message", "Unknown error")
                raise ValueError(f"Template submission failed: {error}")
            
            return template
            
        except Exception as e:
            logger.error(f"Failed to submit template: {e}")
            raise
    
    async def check_approval_status(
        self,
        template_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> MessageTemplate:
        """Check and update template approval status."""
        try:
            template = await self.template_repo.get_by_id(template_id, tenant_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            if not template.whatsapp_template_id:
                return template
            
            # Get channel for access token
            channel = await self.channel_repo.get_by_id(template.channel_id, tenant_id)
            if not channel:
                raise ValueError(f"Channel {template.channel_id} not found")
            
            # Check status via WhatsApp API
            # (Implementation depends on WhatsApp API specifics)
            # For now, we'll simulate approval
            
            # Update status
            if template.status == TemplateStatus.PENDING:
                # Simulate approval after some time
                from datetime import timedelta
                if template.submitted_at:
                    time_elapsed = datetime.utcnow() - template.submitted_at
                    if time_elapsed > timedelta(hours=2):
                        template.approve(template.whatsapp_template_id)
                        await self.template_repo.update(template)
                        
                        # Publish event
                        event = TemplateApproved(
                            event_id=uuid.uuid4(),
                            aggregate_id=template.id,
                            tenant_id=tenant_id,
                            occurred_at=datetime.utcnow(),
                            template_name=template.name,
                            whatsapp_template_id=template.whatsapp_template_id
                        )
                        await self.event_bus.publish(event)
                        
                        logger.info(f"Template {template_id} approved")
            
            return template
            
        except Exception as e:
            logger.error(f"Failed to check approval: {e}")
            raise
    
    async def list_templates(
        self,
        channel_id: uuid.UUID,
        tenant_id: uuid.UUID,
        status_filter: Optional[str] = None
    ) -> List[MessageTemplate]:
        """List templates for a channel."""
        return await self.template_repo.list_by_channel(
            channel_id,
            tenant_id,
            status_filter
        )
    
    async def get_template(
        self,
        template_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> Optional[MessageTemplate]:
        """Get template by ID."""
        return await self.template_repo.get_by_id(template_id, tenant_id)
    
    async def delete_template(
        self,
        template_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> None:
        """Delete a template."""
        try:
            template = await self.template_repo.get_by_id(template_id, tenant_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            if template.status != TemplateStatus.DRAFT:
                raise ValueError("Can only delete draft templates")
            
            await self.template_repo.delete(template_id, tenant_id)
            
            logger.info(f"Template {template_id} deleted")
            
        except Exception as e:
            logger.error(f"Failed to delete template: {e}")
            raise
    
    def _build_whatsapp_template(self, template: MessageTemplate) -> Dict[str, Any]:
        """Build WhatsApp API template format."""
        components = []
        
        for comp in template.components:
            wa_comp = {
                "type": comp.type
            }
            
            if comp.text:
                wa_comp["text"] = comp.text
            if comp.format:
                wa_comp["format"] = comp.format
            if comp.example:
                wa_comp["example"] = {"body_text": [comp.example]}
            if comp.buttons:
                wa_comp["buttons"] = comp.buttons
            
            components.append(wa_comp)
        
        return {
            "name": template.name,
            "language": template.language,
            "category": template.category.value.upper(),
            "components": components
        }