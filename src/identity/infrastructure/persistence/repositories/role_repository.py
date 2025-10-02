"""
Role Repository Implementation
"""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.sqlalchemy_repository import SQLAlchemyRepository
from src.identity.domain.entities.role import Role
from src.identity.domain.value_objects.permission import Permission
from src.identity.infrastructure.persistence.models.role_model import RoleModel


class RoleRepository(SQLAlchemyRepository[Role, RoleModel]):
    """
    Role repository implementation.
    
    Handles RBAC role persistence.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session=session,
            model_class=RoleModel,
            entity_class=Role,
        )
    
    def _to_entity(self, model: RoleModel) -> Role:
        """Convert ORM model to domain entity"""
        permissions = {Permission(p) for p in model.permissions}
        
        return Role(
            id=model.id,
            organization_id=model.organization_id,
            name=model.name,
            description=model.description,
            permissions=permissions,
            is_system=model.is_system,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: Role) -> RoleModel:
        """Convert domain entity to ORM model"""
        permissions_list = [p.value for p in entity.permissions]
        
        return RoleModel(
            id=entity.id,
            organization_id=entity.organization_id,
            name=entity.name,
            description=entity.description,
            permissions=permissions_list,
            is_system=entity.is_system,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
    
    async def get_by_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> Optional[Role]:
        """
        Get role by name within organization.
        
        Args:
            organization_id: Organization UUID
            name: Role name
            
        Returns:
            Role if found, None otherwise
        """
        stmt = select(RoleModel).where(
            RoleModel.organization_id == organization_id,
            RoleModel.name == name,
        )
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        return self._to_entity(model) if model else None
    
    async def find_by_organization(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Role]:
        """
        Find all roles for an organization.
        
        Args:
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of roles
        """
        stmt = (
            select(RoleModel)
            .where(RoleModel.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .order_by(RoleModel.name)
        )
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]
    
    async def find_system_roles(self) -> Sequence[Role]:
        """
        Find all system roles.
        
        Returns:
            List of system roles
        """
        stmt = select(RoleModel).where(RoleModel.is_system == True)
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        
        return [self._to_entity(model) for model in models]