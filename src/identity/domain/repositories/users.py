# src/identity/domain/repositories/users.py
"""
User repository interface (port).

Defines contract for user data access without implementation details.
"""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from identity.domain.entities.user import User

from ..types import UserId, TenantId
from ..value_objects.email import Email
from ..value_objects.role import Role


class UserRepository(ABC):
    """
    Repository interface for user aggregate root.
    
    All methods are async and raise domain exceptions on errors.
    Implementations must enforce RLS and tenant isolation.
    """
    
    @abstractmethod
    async def get_by_id(self, user_id: UserId, tenant_id: TenantId) -> Optional["User"]:
        """
        Retrieve user by ID within tenant scope.
        
        Args:
            user_id: Unique user identifier
            tenant_id: Tenant context for RLS
            
        Returns:
            User entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def get_by_email(self, email: Email, tenant_id: TenantId) -> Optional["User"]:
        """
        Retrieve user by email within tenant scope.
        
        Args:
            email: User email address
            tenant_id: Tenant context for RLS
            
        Returns:
            User entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def create(self, user: "User") -> "User":
        """
        Persist new user.
        
        Args:
            user: User entity to create
            
        Returns:
            Created user with assigned ID and timestamps
            
        Raises:
            ConflictError: If email already exists in tenant
            ValidationError: If user data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def update(self, user: "User") -> "User":
        """
        Update existing user.
        
        Args:
            user: User entity with updates
            
        Returns:
            Updated user with new timestamps
            
        Raises:
            NotFoundInDomain: If user doesn't exist
            ConflictError: If email conflicts with another user
            ValidationError: If update data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def list_by_tenant(self, tenant_id: TenantId, limit: int = 100, offset: int = 0) -> list["User"]:
        """
        List users within tenant with pagination.
        
        Args:
            tenant_id: Tenant context for RLS
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List of users, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def list_by_role(self, tenant_id: TenantId, role: Role) -> list["User"]:
        """
        List users with specific role within tenant.
        
        Args:
            tenant_id: Tenant context for RLS
            role: Role to filter by
            
        Returns:
            List of users with the role, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def exists_by_email(self, email: Email, tenant_id: TenantId, exclude_id: Optional[UserId] = None) -> bool:
        """
        Check if email is already taken within tenant.
        
        Args:
            email: Email to check
            tenant_id: Tenant context for RLS
            exclude_id: User ID to exclude from check (for updates)
            
        Returns:
            True if email exists, False otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def count_by_tenant(self, tenant_id: TenantId) -> int:
        """
        Count total users within tenant.
        
        Args:
            tenant_id: Tenant context for RLS
            
        Returns:
            Total number of users in tenant
            
        Raises:
            DomainError: On data access errors
        """
        ...