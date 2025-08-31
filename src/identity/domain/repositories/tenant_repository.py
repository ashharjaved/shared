# src/identity/domain/repositories/tenant_repository.py

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.identity.domain.entities.tenant import Tenant


class TenantRepository(ABC):
    """
    Repository interface for tenant operations.
    
    Provides methods to manage tenant entities with proper
    abstractions for data access.
    """
    
    @abstractmethod
    async def create(self, tenant: Tenant) -> Tenant:
        """
        Create a new tenant.
        
        Args:
            tenant: Tenant entity to create
            
        Returns:
            The created tenant entity
            
        Raises:
            ConflictError: If tenant name already exists
        """
        pass
    
    @abstractmethod
    async def find_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """
        Find tenant by ID.
        
        Args:
            tenant_id: The tenant ID to search for
            
        Returns:
            Tenant entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[Tenant]:
        """
        Find tenant by name.
        
        Args:
            name: The tenant name to search for
            
        Returns:
            Tenant entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def list_children(self, parent_id: UUID) -> List[Tenant]:
        """
        List all child tenants of a parent tenant.
        
        Args:
            parent_id: The parent tenant ID
            
        Returns:
            List of child tenant entities
        """
        pass
    
    @abstractmethod
    async def update(self, tenant: Tenant) -> Tenant:
        """
        Update an existing tenant.
        
        Args:
            tenant: Tenant entity with updates
            
        Returns:
            The updated tenant entity
            
        Raises:
            NotFoundError: If tenant doesn't exist
        """
        pass
    
    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        """
        List all tenants with pagination.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of tenant entities
        """
        pass