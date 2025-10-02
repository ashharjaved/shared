"""
RLS Verification Utilities
Ensures RLS context is set before tenant-scoped queries
"""
from functools import wraps
from typing import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class RLSNotSetError(Exception):
    """Raised when RLS context is not set for tenant-scoped operation"""
    
    def __init__(self) -> None:
        super().__init__(
            "RLS context not set. Call uow.set_tenant_context() before tenant-scoped operations."
        )


async def verify_rls_context(session: AsyncSession) -> bool:
    """
    Verify that RLS context (GUC) is set on the session.
    
    Args:
        session: SQLAlchemy async session
        
    Returns:
        True if RLS context is set, False otherwise
    """
    try:
        result = await session.execute(
            text("SELECT current_setting('app.current_org_id', true)")
        )
        value = result.scalar_one_or_none()
        return value is not None and value != ''
    except Exception:
        return False


def require_rls_context(func: Callable) -> Callable:
    """
    Decorator to require RLS context before executing repository method.
    
    Raises RLSNotSetError if context is not set.
    
    Usage:
        @require_rls_context
        async def get_by_id(self, user_id: UUID) -> Optional[User]:
            # RLS context verified before this executes
            ...
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # Check if RLS context is set
        if not await verify_rls_context(self.session):
            logger.error(
                f"RLS context not set for {func.__name__}",
                extra={
                    "repository": self.__class__.__name__,
                    "method": func.__name__,
                },
            )
            raise RLSNotSetError()
        
        return await func(self, *args, **kwargs)
    
    return wrapper