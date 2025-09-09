# src/identity/domain/repositories/tenants.py
"""
Tenant repository interface (port).

Defines contract for tenant data access without implementation details.
"""

from abc import ABC, abstractmethod
from typing import Optional
from identity.domain.entities import Tenant

from ..types import TenantId

class TenantRepository(ABC):
    """
    Repository interface for tenant aggregate root.
    
    All methods are async and raise domain exceptions on errors.
    Implementations must enforce RLS and tenant isolation.
    """
    
    @abstractmethod
    async def get_by_id(self, tenant_id: TenantId) -> Optional["Tenant"]:
        """
        Retrieve tenant by ID.
        
        Args:
            tenant_id: Unique tenant identifier
            
        Returns:
            Tenant entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional["Tenant"]:
        """
        Retrieve tenant by unique slug.
        
        Args:
            slug: Unique tenant slug
            
        Returns:
            Tenant entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def create(self, tenant: "Tenant") -> "Tenant":
        """
        Persist new tenant.
        
        Args:
            tenant: Tenant entity to create
            
        Returns:
            Created tenant with assigned ID and timestamps
            
        Raises:
            ConflictError: If slug already exists
            ValidationError: If tenant data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def update(self, tenant: "Tenant") -> "Tenant":
        """
        Update existing tenant.
        
        Args:
            tenant: Tenant entity with updates
            
        Returns:
            Updated tenant with new timestamps
            
        Raises:
            NotFoundInDomain: If tenant doesn't exist
            ConflictError: If slug conflicts with another tenant
            ValidationError: If update data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def list_by_parent(self, parent_id: Optional[TenantId] = None) -> list["Tenant"]:
        """
        List tenants by parent ID.
        
        Args:
            parent_id: Parent tenant ID, None for root tenants
            
        Returns:
            List of child tenants, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def get_hierarchy_path(self, tenant_id: TenantId) -> list["Tenant"]:
        """
        Get full hierarchy path from root to specified tenant.
        
        Args:
            tenant_id: Target tenant ID
            
        Returns:
            List of tenants from root to target (inclusive)
            
        Raises:
            NotFoundInDomain: If tenant doesn't exist
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def exists_by_slug(self, slug: str, exclude_id: Optional[TenantId] = None) -> bool:
        """
        Check if slug is already taken.
        
        Args:
            slug: Slug to check
            exclude_id: Tenant ID to exclude from check (for updates)
            
        Returns:
            True if slug exists, False otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...