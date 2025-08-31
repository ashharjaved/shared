# src/identity/domain/repositories/user_repository.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.identity.domain.entities.user import User
from src.shared.roles import Role


class UserRepository(ABC):
    """
    Repository interface for user operations.
    
    Provides methods to manage user entities with proper
    tenant isolation and security controls.
    """
    
    @abstractmethod
    async def find_by_email(self, email: str, tenant_id: UUID) -> Optional[User]:
        """
        Find user by email within a tenant.
        
        Args:
            email: User email address
            tenant_id: Tenant ID for isolation
            
        Returns:
            User entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Find user by ID (with RLS enforcement).
        
        Args:
            user_id: The user ID to search for
            
        Returns:
            User entity if found and accessible, None otherwise
        """
        pass
    
    @abstractmethod
    async def create(self, user: User) -> User:
        """
        Create a new user.
        
        Args:
            user: User entity to create
            
        Returns:
            The created user entity
            
        Raises:
            ConflictError: If email already exists in tenant
        """
        pass
    
    @abstractmethod
    async def update(self, user: User) -> User:
        """
        Update an existing user.
        
        Args:
            user: User entity with updates
            
        Returns:
            The updated user entity
            
        Raises:
            NotFoundError: If user doesn't exist or not accessible
        """
        pass
    
    @abstractmethod
    async def update_last_login(self, user_id: UUID, login_time: datetime) -> None:
        """
        Update user's last login timestamp.
        
        Args:
            user_id: The user ID
            login_time: The login timestamp
        """
        pass
    
    @abstractmethod
    async def increment_failed_logins(self, user_id: UUID) -> int:
        """
        Increment failed login attempts counter.
        
        Args:
            user_id: The user ID
            
        Returns:
            The new failed login attempts count
        """
        pass
    
    @abstractmethod
    async def reset_failed_logins(self, user_id: UUID) -> None:
        """
        Reset failed login attempts counter to zero.
        
        Args:
            user_id: The user ID
        """
        pass
    
    @abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: UUID,
        role: Optional[Role] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """
        List users in a tenant with optional role filtering.
        
        Args:
            tenant_id: The tenant ID
            role: Optional role filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of user entities
        """
        pass