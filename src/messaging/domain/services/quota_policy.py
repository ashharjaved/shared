# src/messaging/domain/services/quota_policy.py
"""Monthly quota policy enforcement."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ..types import TenantId


class QuotaStorage(Protocol):
    """Protocol for quota usage storage."""
    
    def get_monthly_usage(self, tenant_id: TenantId, year_month: str) -> int:
        """Get current monthly usage for tenant."""
        ...
    
    def increment_monthly_usage(self, tenant_id: TenantId, year_month: str, count: int) -> int:
        """Increment monthly usage and return new total."""
        ...


@dataclass(frozen=True, slots=True) 
class QuotaResult:
    """Result of quota check."""
    allowed: bool
    current_usage: int
    limit: int
    remaining: int


class QuotaPolicy:
    """
    Domain service for monthly quota enforcement.
    
    Tracks and enforces per-tenant monthly message limits.
    Pure domain logic without infrastructure dependencies.
    
    Example:
        policy = QuotaPolicy(storage)
        result = policy.check_quota(tenant_id, 1000, planned_messages=5)
        if not result.allowed:
            raise QuotaExceeded("Monthly quota exceeded", tenant_id)
    """
    
    def __init__(self, storage: QuotaStorage) -> None:
        self._storage = storage
    
    def is_within_monthly_quota(self, tenant_id: TenantId, used: int, limit: int) -> bool:
        """
        Check if current usage is within monthly quota.
        
        Args:
            tenant_id: Tenant to check
            used: Current month usage
            limit: Monthly limit
            
        Returns:
            True if within quota
        """
        return used < limit
    
    def will_exceed_monthly_quota(
        self, 
        tenant_id: TenantId, 
        planned: int, 
        used: int, 
        limit: int
    ) -> bool:
        """
        Check if planned usage will exceed monthly quota.
        
        Args:
            tenant_id: Tenant to check  
            planned: Number of messages planned to send
            used: Current month usage
            limit: Monthly limit
            
        Returns:
            True if planned usage would exceed quota
        """
        return (used + planned) > limit
    
    def check_quota(
        self,
        tenant_id: TenantId,
        limit: int,
        planned_messages: int = 1
    ) -> QuotaResult:
        """
        Check quota with current storage state.
        
        Args:
            tenant_id: Tenant to check
            limit: Monthly message limit
            planned_messages: Number of messages about to send
            
        Returns:
            QuotaResult with allow/deny decision
        """
        year_month = datetime.utcnow().strftime("%Y-%m")
        current_usage = self._storage.get_monthly_usage(tenant_id, year_month)
        
        would_exceed = self.will_exceed_monthly_quota(
            tenant_id, planned_messages, current_usage, limit
        )
        
        return QuotaResult(
            allowed=not would_exceed,
            current_usage=current_usage,
            limit=limit,
            remaining=max(0, limit - current_usage)
        )