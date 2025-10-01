# src/identity/infrastructure/repositories/tenant_repository_impl.py
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.identity.domain.types import TenantId
from src.identity.infrastructure.Mappers.tenant_mapper import TenantMapper
from src.shared.database.base_repository import BaseRepository
from src.identity.domain.entities.tenant import Tenant
from src.identity.domain.repositories.tenant_repository import TenantRepository
from src.identity.infrastructure.models.tenant_model import TenantModel
from src.shared.exceptions import ConflictError  # BaseRepository already maps most errors


class TenantRepositoryImpl(
    BaseRepository[TenantModel, Tenant, TenantId], TenantRepository
):
    """
    SQLAlchemy implementation of tenant repository.

    Uses BaseRepository for common CRUD; avoids committing inside the repo
    (UoW / service decides when to commit).
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session,  TenantModel, TenantMapper())

    # ---- Create -------------------------------------------------------------
    async def create(self, tenant: Tenant) -> Tenant:
        """
        Create a new tenant.
        Relies on BaseRepository.create() which does add/flush/refresh (no commit).
        """
        try:
            return await super().create(tenant)
        except IntegrityError as e:
            await self._session.rollback()
            # Handle name uniqueness gracefully
            if "uq_tenants_name" in str(e) or "name" in str(e):
                raise ConflictError(f"Tenant name '{tenant.name}' already exists") from e
            raise

    # ---- Reads --------------------------------------------------------------
    async def find_by_id(self, tenant_id: TenantId) -> Optional[Tenant]:
        """Find tenant by ID."""
        return await super().get_by_id(tenant_id)

    async def find_by_name(self, name: str) -> Optional[Tenant]:
        """Find tenant by name."""
        return await self.get_one(name=name)

    async def list_children(self, parent_id: UUID) -> List[Tenant]:
        """List all child tenants of a parent tenant."""
        return await self.list(parent_tenant_id=parent_id)

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        """List all tenants with pagination."""
        return await self.list(limit=limit, offset=offset)

    # ---- Update -------------------------------------------------------------
    async def update(self, tenant: Tenant) -> Tenant:
        """
        Update an existing tenant.
        Delegates to BaseRepository.update() (merge/flush/refresh).
        """
        try:
            return await super().update(tenant)
        except IntegrityError as e:
            await self._session.rollback()
            if "uq_tenants_name" in str(e) or "name" in str(e):
                raise ConflictError(f"Tenant name '{tenant.name}' already exists") from e
            raise
