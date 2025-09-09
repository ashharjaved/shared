# src/identity/domain/repositories/subscriptions.py
"""
Subscription repository interface (port).

Defines contract for tenant plan subscription data access.
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from identity.domain.entities.subscription import TenantPlanSubscription

from ..types import SubscriptionId, TenantId, PlanId


class SubscriptionRepository(ABC):
    """
    Repository interface for tenant plan subscription entity.
    
    Subscriptions link tenants to plans with lifecycle management.
    All methods are async and raise domain exceptions on errors.
    """
    
    @abstractmethod
    async def get_by_id(self, subscription_id: SubscriptionId) -> Optional["TenantPlanSubscription"]:
        """
        Retrieve subscription by ID.
        
        Args:
            subscription_id: Unique subscription identifier
            
        Returns:
            Subscription entity if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def get_active_by_tenant(self, tenant_id: TenantId) -> Optional["TenantPlanSubscription"]:
        """
        Get active subscription for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Active subscription if found, None otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def create(self, subscription: "TenantPlanSubscription") -> "TenantPlanSubscription":
        """
        Persist new subscription.
        
        Args:
            subscription: Subscription entity to create
            
        Returns:
            Created subscription with assigned ID
            
        Raises:
            ConflictError: If tenant already has active subscription
            ValidationError: If subscription data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def update(self, subscription: "TenantPlanSubscription") -> "TenantPlanSubscription":
        """
        Update existing subscription.
        
        Args:
            subscription: Subscription entity with updates
            
        Returns:
            Updated subscription
            
        Raises:
            NotFoundInDomain: If subscription doesn't exist
            ValidationError: If update data is invalid
            DomainError: On other data access errors
        """
        ...
    
    @abstractmethod
    async def list_by_tenant(self, tenant_id: TenantId) -> list["TenantPlanSubscription"]:
        """
        List all subscriptions for tenant (current and historical).
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of subscriptions ordered by start_at DESC, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def list_by_plan(self, plan_id: PlanId) -> list["TenantPlanSubscription"]:
        """
        List all subscriptions for plan.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            List of subscriptions, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def list_expiring_soon(self, days_ahead: int = 7) -> list["TenantPlanSubscription"]:
        """
        List subscriptions expiring within specified days.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring subscriptions, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def list_past_due(self, as_of: Optional[datetime] = None) -> list["TenantPlanSubscription"]:
        """
        List subscriptions that are past due.
        
        Args:
            as_of: Reference timestamp, defaults to now()
            
        Returns:
            List of past due subscriptions, empty if none found
            
        Raises:
            DomainError: On data access errors
        """
        ...
    
    @abstractmethod
    async def has_active_subscription(self, tenant_id: TenantId) -> bool:
        """
        Check if tenant has an active subscription.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if tenant has active subscription, False otherwise
            
        Raises:
            DomainError: On data access errors
        """
        ...