from __future__ import annotations

import inspect
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Union

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.shared_.database.database import get_async_session
from src.shared_.database.types import TenantContext
from src.shared_.database.rls import apply_rls_locals, tenant_context_from_ctxvars

logger = structlog.get_logger(__name__)


async def run_in_transaction(
    operation: Callable[[AsyncSession, Any], Any] | Callable[[AsyncSession, Any], Awaitable[Any]],
    tenant_context: Optional[TenantContext] = None,
    *args,
    **kwargs,
) -> Any:
    start = time.time()
    try:
        _ctx = tenant_context or tenant_context_from_ctxvars()
        async with get_async_session() as session:
            async with session.begin():
                if _ctx and _ctx.tenant_id:
                    await apply_rls_locals(session, _ctx)

                if inspect.iscoroutinefunction(operation):
                    result = await operation(session, *args, **kwargs)
                else:
                    result = operation(session, *args, **kwargs)

        logger.debug("Transaction completed", duration_ms=int((time.time() - start) * 1000))
        return result
    except Exception as e:
        logger.error("Transaction failed", error=str(e), duration_ms=int((time.time() - start) * 1000))
        raise


async def execute_query(
    query: Union[str, sa.sql.Executable],
    params: Optional[Dict[str, Any]] = None,
    tenant_context: Optional[TenantContext] = None,
):    
    async def _op(session: AsyncSession, *args, **kwargs) -> Any:
        if isinstance(query, str):
            return await session.execute(sa.text(query), params or {})
        return await session.execute(query, params or {})

    return await run_in_transaction(_op, tenant_context)


async def get_tenant_from_db_helper() -> Optional[str]:
    try:
        async with get_async_session() as session:
            res = await session.execute(sa.text("SELECT jwt_tenant()"))
            return str(res.scalar_one_or_none() or "")
    except Exception:
        logger.warning("Could not retrieve tenant from context", exc_info=True)
        return None
