# src/identity/domain/repositories/plans.py
"""
Plan repository interface (port).

Defines contract for plan data access without implementation details.
"""

from abc import ABC, abstractmethod
from typing import Optional

from identity.domain.entities import Plan

from ..types import PlanId


class PlanRepository(ABC):
    """
    Repository interface for plan entity.
    
    Plans are global (not tenant-scoped) and define subscription tiers.
    All methods are async and raise domain exceptions on errors.
    """
    
    @abstractmethod
    async def get_by_id(self, plan_id: PlanId) -> Optional["Plan"]:
        """
        Retrieve plan by ID.
        
        Args:
            plan_id: Unique plan identifier
            
        Returns:
            Plan entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional["Plan"]:
        """
        Retrieve plan by unique slug.
        
        Args:
            slug: Unique plan slug (e.g., 'basic', 'pro', 'enterprise')
            
        Returns:
            Plan entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def create(self, plan: "Plan") -> "Plan":
        """
        Persist new plan.
        
        Args:
            plan: Plan entity to create
            
        Returns:
            Created plan with assigned ID
            
        Raises:
            ConflictError: If slug already exists
            ValidationError: If plan data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def update(self, plan: "Plan") -> "Plan":
        """
        Update existing plan.
        
        Args:
            plan: Plan entity with updates
            
        Returns:
            Updated plan
            
        Raises:
            NotFoundInDomain: If plan doesn't exist
            ConflictError: If slug conflicts with another plan
            ValidationError: If update data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def list_active(self) -> list["Plan"]:
        """
        List all active plans.
        
        Returns:
            List of active plans, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def list_all(self) -> list["Plan"]:
        """
        List all plans (active and inactive).
        
        Returns:
            List of all plans, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def exists_by_slug(self, slug: str, exclude_id: Optional[PlanId] = None) -> bool:
        """
        Check if slug is already taken.
        
        Args:
            slug: Slug to check
            exclude_id: Plan ID to exclude from check (for updates)
            
        Returns:
            True if slug exists, False otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...