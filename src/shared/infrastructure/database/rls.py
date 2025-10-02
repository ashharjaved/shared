"""
Centralized Row-Level Security (RLS) Enforcement
Sets GUC (Grand Unified Configuration) variables for PostgreSQL RLS
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class RLSManager:
    """
    Centralized manager for Row-Level Security enforcement.
    
    Sets PostgreSQL session variables (GUC) for RLS policies:
    - app.current_org_id: Organization/tenant ID
    - app.current_user_id: User ID
    - app.current_roles: JSON array of roles
    
    CRITICAL: This is the ONLY place where RLS/GUC should be set.
    Do NOT duplicate this logic in repositories or modules.
    """
    
    @staticmethod
    async def set_tenant_context(
        session: AsyncSession,
        organization_id: UUID,
        user_id: UUID | None = None,
        roles: list[str] | None = None,
    ) -> None:
        """
        Set tenant context for RLS enforcement.
        
        Must be called at the start of every request that requires tenant isolation.
        
        Args:
            session: Active async database session
            organization_id: Organization/tenant UUID
            user_id: Current user UUID (optional)
            roles: List of role names (optional)
            
        Raises:
            ValueError: If organization_id is None
        """
        if organization_id is None:
            raise ValueError("organization_id is required for RLS context")
        
        try:
            # Set organization ID (required for all RLS policies)
            await session.execute(
                text("SET LOCAL app.current_org_id = :org_id"),
                {"org_id": str(organization_id)}
            )
            
            # Set user ID if provided
            if user_id is not None:
                await session.execute(
                    text("SET LOCAL app.current_user_id = :user_id"),
                    {"user_id": str(user_id)}
                )
            
            # Set roles if provided (as JSON array)
            if roles:
                roles_json = str(roles).replace("'", '"')  # Convert to JSON format
                await session.execute(
                    text("SET LOCAL app.current_roles = :roles"),
                    {"roles": roles_json}
                )
            
            logger.debug(
                "RLS context set",
                extra={
                    "organization_id": str(organization_id),
                    "user_id": str(user_id) if user_id else None,
                    "roles": roles,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to set RLS context",
                extra={
                    "error": str(e),
                    "organization_id": str(organization_id),
                },
            )
            raise
    
    @staticmethod
    async def clear_tenant_context(session: AsyncSession) -> None:
        """
        Clear tenant context (reset GUC variables).
        
        Should be called at the end of request processing.
        
        Args:
            session: Active async database session
        """
        try:
            await session.execute(text("RESET app.current_org_id"))
            await session.execute(text("RESET app.current_user_id"))
            await session.execute(text("RESET app.current_roles"))
            
            logger.debug("RLS context cleared")
        except Exception as e:
            logger.error(f"Failed to clear RLS context: {e}")
            raise
    
    @staticmethod
    async def get_current_org_id(session: AsyncSession) -> UUID | None:
        """
        Get current organization ID from session context.
        
        Args:
            session: Active async database session
            
        Returns:
            Current organization UUID or None
        """
        try:
            result = await session.execute(
                text("SELECT current_setting('app.current_org_id', true)")
            )
            org_id_str = result.scalar()
            return UUID(org_id_str) if org_id_str else None
        except Exception:
            return None