"""Template repository implementation."""

from datetime import datetime
from typing import Optional, List, cast
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
import logging

from src.messaging.domain.interfaces.repositories import TemplateRepository
from src.messaging.domain.entities.template import (
    MessageTemplate, TemplateStatus, TemplateCategory, TemplateComponent
)
from src.messaging.infrastructure.models.template_model import MessageTemplateModel

logger = logging.getLogger(__name__)


class TemplateRepositoryImpl(TemplateRepository):
    """Template repository implementation using SQLAlchemy."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, template: MessageTemplate) -> MessageTemplate:
        """Create a new template."""
        try:
            # Convert components to JSON-serializable format
            components_data = []
            for comp in template.components:
                comp_dict = {
                    "type": comp.type,
                    "format": comp.format,
                    "text": comp.text,
                    "example": comp.example,
                    "buttons": comp.buttons
                }
                components_data.append(comp_dict)
            
            model = MessageTemplateModel(
                id=template.id,
                tenant_id=template.tenant_id,
                channel_id=template.channel_id,
                name=template.name,
                language=template.language,
                category=template.category,
                status=template.status,
                components=components_data,
                whatsapp_template_id=template.whatsapp_template_id,
                rejection_reason=template.rejection_reason,
                created_at=template.created_at,
                updated_at=template.updated_at,
                submitted_at=template.submitted_at,
                approved_at=template.approved_at
            )
            
            self.session.add(model)
            await self.session.flush()
            
            return template
            
        except Exception as e:
            logger.error(f"Failed to create template: {e}")
            raise
    
    async def get_by_id(self, template_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[MessageTemplate]:
        """Get template by ID."""
        try:
            stmt = select(MessageTemplateModel).where(
                and_(
                    MessageTemplateModel.id == template_id,
                    MessageTemplateModel.tenant_id == tenant_id,
                    MessageTemplateModel.deleted_at.is_(None)
                )
            )
            
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                return self._to_entity(model)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get template: {e}")
            raise
    
    async def get_by_name(
        self, 
        name: str, 
        channel_id: uuid.UUID, 
        tenant_id: uuid.UUID
    ) -> Optional[MessageTemplate]:
        """Get template by name."""
        try:
            stmt = select(MessageTemplateModel).where(
                and_(
                    MessageTemplateModel.name == name,
                    MessageTemplateModel.channel_id == channel_id,
                    MessageTemplateModel.tenant_id == tenant_id,
                    MessageTemplateModel.deleted_at.is_(None)
                )
            )
            
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                return self._to_entity(model)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get template by name: {e}")
            raise
    
    async def list_by_channel(
        self,
        channel_id: uuid.UUID,
        tenant_id: uuid.UUID,
        status_filter: Optional[str] = None
    ) -> List[MessageTemplate]:
        """List templates for a channel."""
        try:
            conditions = [
                MessageTemplateModel.channel_id == channel_id,
                MessageTemplateModel.tenant_id == tenant_id,
                MessageTemplateModel.deleted_at.is_(None)
            ]
            
            if status_filter:
                conditions.append(MessageTemplateModel.status == status_filter)
            
            stmt = select(MessageTemplateModel).where(
                and_(*conditions)
            ).order_by(MessageTemplateModel.created_at.desc())
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            return [self._to_entity(model) for model in models]
            
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            raise
    
    async def update(self, template: MessageTemplate) -> MessageTemplate:
        """Update template."""
        try:
            # Convert components to JSON
            components_data = []
            for comp in template.components:
                comp_dict = {
                    "type": comp.type,
                    "format": comp.format,
                    "text": comp.text,
                    "example": comp.example,
                    "buttons": comp.buttons
                }
                components_data.append(comp_dict)
            
            stmt = update(MessageTemplateModel).where(
                and_(
                    MessageTemplateModel.id == template.id,
                    MessageTemplateModel.tenant_id == template.tenant_id
                )
            ).values(
                name=template.name,
                language=template.language,
                category=template.category,
                status=template.status,
                components=components_data,
                whatsapp_template_id=template.whatsapp_template_id,
                rejection_reason=template.rejection_reason,
                updated_at=template.updated_at,
                submitted_at=template.submitted_at,
                approved_at=template.approved_at
            )
            
            await self.session.execute(stmt)
            await self.session.flush()
            
            return template
            
        except Exception as e:
            logger.error(f"Failed to update template: {e}")
            raise
    
    async def delete(self, template_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Soft delete template."""
        try:
            from datetime import datetime
            
            stmt = update(MessageTemplateModel).where(
                and_(
                    MessageTemplateModel.id == template_id,
                    MessageTemplateModel.tenant_id == tenant_id
                )
            ).values(
                deleted_at=datetime.utcnow()
            )
            
            await self.session.execute(stmt)
            await self.session.flush()
            
        except Exception as e:
            logger.error(f"Failed to delete template: {e}")
            raise
    
    def _to_entity(self, model: MessageTemplateModel) -> MessageTemplate:
        """Convert ORM model to domain entity."""
        # Convert JSON components to domain objects
        components = []
        for comp_data in model.components:
            components.append(TemplateComponent(
                type=comp_data.get("type"),
                format=comp_data.get("format"),
                text=comp_data.get("text"),
                example=comp_data.get("example"),
                buttons=comp_data.get("buttons")
            ))
        
        return MessageTemplate(
            id=cast(uuid.UUID, model.id),
            tenant_id=cast(uuid.UUID, model.tenant_id),
            channel_id=cast(uuid.UUID, model.channel_id),
            name=cast(str, model.name),
            language=cast(str, model.language),
            category=cast(TemplateCategory, model.category),
            status=cast(TemplateStatus, model.status),
            components=components,
            whatsapp_template_id=cast(Optional[str], model.whatsapp_template_id),
            rejection_reason=cast(Optional[str], model.rejection_reason),
            created_at=cast(Optional[datetime], model.created_at),
            updated_at=cast(Optional[datetime], model.updated_at),
            submitted_at=cast(Optional[datetime], model.submitted_at),
            approved_at=cast(Optional[datetime], model.approved_at)
        )