# src/messaging/infrastructure/persistence/repositories/template_repository_impl.py
"""
SQLAlchemy Implementation of TemplateRepository
Extends generic SQLAlchemyRepository base class
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.domain.entities.message_template import MessageTemplate
from src.messaging.domain.protocols.template_repository import TemplateRepository
from src.messaging.infrastructure.persistence.models.message_template_model import MessageTemplateModel
from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from shared.infrastructure.database.rls import RLSManager
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class TemplateRepositoryImpl(
    SQLAlchemyRepository[MessageTemplate, MessageTemplateModel], 
    TemplateRepository
):
    """
    SQLAlchemy implementation of TemplateRepository.
    
    Inherits CRUD operations from SQLAlchemyRepository and implements
    domain-specific template queries with RLS enforcement.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        """
        Initialize template repository.
        
        Args:
            session: Active async database session
            tenant_id: Tenant UUID for RLS enforcement
        """
        super().__init__(
            session=session,
            model_class=MessageTemplateModel,
            entity_class=MessageTemplate
        )
        self.tenant_id = tenant_id
    
    # ========================================================================
    # DOMAIN-SPECIFIC QUERIES
    # ========================================================================
    
    async def get_by_name_and_language(
        self, 
        tenant_id: UUID, 
        name: str, 
        language: str
    ) -> Optional[MessageTemplate]:
        """
        Find template by name and language.
        
        Args:
            tenant_id: Organization UUID
            name: Template name
            language: Language code (e.g., 'en', 'es')
            
        Returns:
            MessageTemplate if found, None otherwise
        """
        await RLSManager.set_tenant_context(self.session, tenant_id)
        
        try:
            # Use inherited find_one with multiple filters
            template = await self.find_one(
                tenant_id=tenant_id,
                name=name,
                language=language
            )
            
            if template:
                logger.debug(
                    "Template found by name and language",
                    extra={
                        "tenant_id": str(tenant_id),
                        "name": name,
                        "language": language,
                        "template_id": str(template.id)
                    }
                )
            
            return template
            
        except Exception as e:
            logger.error(
                "Failed to get template by name and language",
                extra={
                    "error": str(e),
                    "tenant_id": str(tenant_id),
                    "name": name,
                    "language": language
                }
            )
            raise
    
    async def list_by_tenant(
        self, 
        tenant_id: UUID, 
        status: Optional[str] = None
    ) -> List[MessageTemplate]:
        """
        List templates for a tenant, optionally filtered by status.
        
        Args:
            tenant_id: Organization UUID
            status: Filter by status (pending, approved, rejected) - optional
            
        Returns:
            List of message templates ordered by creation time (newest first)
        """
        await RLSManager.set_tenant_context(self.session, tenant_id)
        
        try:
            # Build filters
            filters = {"tenant_id": tenant_id}
            if status:
                filters["status"] = status
            
            # Use inherited find_all with filters
            templates = await self.find_all(
                order_by="created_at",
                **filters
            )
            
            # Reverse to get newest first
            result = list(reversed(list(templates)))
            
            logger.debug(
                "Listed templates for tenant",
                extra={
                    "tenant_id": str(tenant_id),
                    "status_filter": status,
                    "count": len(result)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to list templates for tenant",
                extra={
                    "error": str(e),
                    "tenant_id": str(tenant_id),
                    "status": status
                }
            )
            raise
    
    async def list_approved(self, tenant_id: UUID) -> List[MessageTemplate]:
        """
        List all approved templates for a tenant.
        
        Args:
            tenant_id: Organization UUID
            
        Returns:
            List of approved message templates
        """
        return await self.list_by_tenant(tenant_id, status="approved")
    
    async def list_by_category(
        self, 
        tenant_id: UUID, 
        category: str
    ) -> List[MessageTemplate]:
        """
        List templates by category.
        
        Args:
            tenant_id: Organization UUID
            category: Template category (marketing, utility, authentication, etc.)
            
        Returns:
            List of templates in the given category
        """
        await RLSManager.set_tenant_context(self.session, tenant_id)
        
        try:
            templates = await self.find_all(
                tenant_id=tenant_id,
                category=category,
                order_by="created_at"
            )
            
            result = list(reversed(list(templates)))
            
            logger.debug(
                "Listed templates by category",
                extra={
                    "tenant_id": str(tenant_id),
                    "category": category,
                    "count": len(result)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to list templates by category",
                extra={
                    "error": str(e),
                    "tenant_id": str(tenant_id),
                    "category": category
                }
            )
            raise
    
    async def count_by_status(self, tenant_id: UUID, status: str) -> int:
        """
        Count templates by status.
        
        Args:
            tenant_id: Organization UUID
            status: Template status
            
        Returns:
            Count of templates with given status
        """
        await RLSManager.set_tenant_context(self.session, tenant_id)
        
        try:
            count = await self.count(
                tenant_id=tenant_id,
                status=status
            )
            
            logger.debug(
                "Counted templates by status",
                extra={
                    "tenant_id": str(tenant_id),
                    "status": status,
                    "count": count
                }
            )
            
            return count
            
        except Exception as e:
            logger.error(
                "Failed to count templates by status",
                extra={
                    "error": str(e),
                    "tenant_id": str(tenant_id),
                    "status": status
                }
            )
            raise
    
    # ========================================================================
    # OVERRIDE METHODS WITH RLS ENFORCEMENT
    # ========================================================================
    
    async def get_by_id(self, template_id: UUID) -> Optional[MessageTemplate]:
        """Retrieve template by ID with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        return await super().get_by_id(template_id)
    
    async def add(self, entity: MessageTemplate) -> MessageTemplate:
        """Add new template with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().add(entity)
    
    async def update(self, entity: MessageTemplate) -> MessageTemplate:
        """Update template with RLS enforcement."""
        await RLSManager.set_tenant_context(self.session, entity.tenant_id)
        return await super().update(entity)
    
    async def delete(self, template_id: UUID) -> bool:
        """
        Soft-delete template by marking status as deleted.
        
        Args:
            template_id: Template UUID
            
        Returns:
            True if deleted, False if not found
        """
        await RLSManager.set_tenant_context(self.session, self.tenant_id)
        
        try:
            # Find the template first
            template = await self.get_by_id(template_id)
            if not template:
                return False
            
            # Update status to deleted instead of hard delete
            template.status = "deleted"
            await self.update(template)
            
            logger.debug(
                "Template soft-deleted",
                extra={
                    "template_id": str(template_id),
                    "tenant_id": str(self.tenant_id)
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete template",
                extra={
                    "error": str(e),
                    "template_id": str(template_id)
                }
            )
            raise
    
    # ========================================================================
    # ENTITY <-> MODEL MAPPING
    # ========================================================================
    
    def _to_entity(self, model: MessageTemplateModel) -> MessageTemplate:
        """Convert ORM model to domain entity."""
        return MessageTemplate(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            language=model.language,
            category=model.category,
            body_text=model.body_text,
            status=model.status,
            header_text=model.header_text,
            footer_text=model.footer_text,
            buttons=model.buttons or [],
            variables=model.variables or [],
            rejection_reason=model.rejection_reason,
            wa_template_id=model.wa_template_id,
            approved_at=model.approved_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: MessageTemplate) -> MessageTemplateModel:
        """Convert domain entity to ORM model."""
        return MessageTemplateModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            language=entity.language,
            category=entity.category,
            body_text=entity.body_text,
            status=entity.status,
            header_text=entity.header_text,
            footer_text=entity.footer_text,
            buttons=entity.buttons,
            variables=entity.variables,
            rejection_reason=entity.rejection_reason,
            wa_template_id=entity.wa_template_id,
            approved_at=entity.approved_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )