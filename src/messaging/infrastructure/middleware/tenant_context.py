"""Tenant context middleware for RLS."""

import logging
from typing import List, Optional
from contextvars import ContextVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid

logger = logging.getLogger(__name__)

# Context variables for tenant isolation
tenant_context: ContextVar[Optional[uuid.UUID]] = ContextVar('tenant_context', default=None)
user_context: ContextVar[Optional[uuid.UUID]] = ContextVar('user_context', default=None)


class TenantContextManager:
    """Manager for setting tenant context in database."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def set_tenant_context(
        self,
        tenant_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        roles: Optional[List[str]] = None
    ) -> None:
        """Set tenant context for RLS."""
        try:
            # Set PostgreSQL session variables
            await self.session.execute(
                text("SET LOCAL app.jwt_tenant = :tenant_id"),
                {"tenant_id": str(tenant_id)}
            )
            
            if user_id:
                await self.session.execute(
                    text("SET LOCAL app.user_id = :user_id"),
                    {"user_id": str(user_id)}
                )
            
            if roles:
                await self.session.execute(
                    text("SET LOCAL app.roles = :roles"),
                    {"roles": ','.join(roles)}
                )
            
            # Set context variables
            tenant_context.set(tenant_id)
            if user_id:
                user_context.set(user_id)
            
            logger.debug(f"Set tenant context: {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to set tenant context: {e}")
            raise
    
    async def clear_tenant_context(self) -> None:
        """Clear tenant context."""
        try:
            await self.session.execute(text("RESET app.jwt_tenant"))
            await self.session.execute(text("RESET app.user_id"))
            await self.session.execute(text("RESET app.roles"))
            
            tenant_context.set(None)
            user_context.set(None)
            
        except Exception as e:
            logger.error(f"Failed to clear tenant context: {e}")
            raise
    
    def get_current_tenant(self) -> Optional[uuid.UUID]:
        """Get current tenant from context."""
        return tenant_context.get()
    
    def get_current_user(self) -> Optional[uuid.UUID]:
        """Get current user from context."""
        return user_context.get()