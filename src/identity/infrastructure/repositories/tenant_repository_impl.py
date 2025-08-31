# src/identity/infrastructure/repositories/tenant_repository_impl.py

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.identity.domain.entities.tenant import Tenant
from src.identity.domain.repositories.tenant_repository import TenantRepository
from src.identity.infrastructure.models.tenant_model import TenantModel
from src.shared.exceptions import ConflictError, NotFoundError


class TenantRepositoryImpl(TenantRepository):
    """
    SQLAlchemy implementation of tenant repository.
    
    Handles tenant CRUD operations with proper error handling
    and domain/infrastructure mapping.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def create(self, tenant: Tenant) -> Tenant:
        """Create a new tenant."""
        try:
            model = TenantModel.from_domain(tenant)
            self._session.add(model)
            await self._session.flush()
            await self._session.refresh(model)
            return model.to_domain()
        except IntegrityError as e:
            await self._session.rollback()
            if "uq_tenants_name" in str(e) or "name" in str(e):
                raise ConflictError(f"Tenant name '{tenant.name}' already exists")
            raise ConflictError("Failed to create tenant due to constraint violation")
    
    async def find_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """Find tenant by ID."""
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None
    
    async def find_by_name(self, name: str) -> Optional[Tenant]:
        """Find tenant by name."""
        stmt = select(TenantModel).where(TenantModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None
    
    async def list_children(self, parent_id: UUID) -> List[Tenant]:
        """List all child tenants of a parent tenant."""
        stmt = select(TenantModel).where(TenantModel.parent_tenant_id == parent_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [model.to_domain() for model in models]
    
    async def update(self, tenant: Tenant) -> Tenant:
        """Update an existing tenant."""
        stmt = select(TenantModel).where(TenantModel.id == tenant.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if not model:
            raise NotFoundError(f"Tenant with ID {tenant.id} not found")
        
        try:
            # Update fields
            model.name = tenant.name
            model.type = tenant.type
            model.parent_tenant_id = tenant.parent_tenant_id
            model.plan = tenant.plan
            model.is_active = tenant.is_active
            model.updated_at = tenant.updated_at
            
            await self._session.flush()
            await self._session.refresh(model)
            return model.to_domain()
        except IntegrityError as e:
            await self._session.rollback()
            if "uq_tenants_name" in str(e) or "name" in str(e):
                raise ConflictError(f"Tenant name '{tenant.name}' already exists")
            raise ConflictError("Failed to update tenant due to constraint violation")
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        """List all tenants with pagination."""
        stmt = select(TenantModel).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [model.to_domain() for model in models]