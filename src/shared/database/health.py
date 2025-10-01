from __future__ import annotations

from typing import Any, Dict
from sqlalchemy import text
import structlog

from src.shared.database import get_engine, get_session_factory
from src.shared.database.database import get_async_session

logger = structlog.get_logger(__name__)


class DatabaseHealthCheck:
    @staticmethod
    async def check_connection() -> Dict[str, Any]:
        try:
            engine = get_engine()
            async with engine.begin() as conn:
                res = await conn.execute(text("SELECT 1 AS health_check"))
                row = res.fetchone()
                if not row or row.health_check != 1:
                    return {"healthy": False, "error": "health check failed"}

            payload: Dict[str, Any] = {"healthy": True}
            pool = engine.pool
            for name in ("size", "checkedin", "checkedout", "overflow"):
                if hasattr(pool, name):
                    payload[name if name != "size" else "pool_size"] = getattr(pool, name)()  # type: ignore
            return payload
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {"healthy": False, "error": str(e)}

    @staticmethod
    async def check_rls_functions() -> Dict[str, Any]:
        try:
            async with get_async_session() as session:
                res = await session.execute(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'jwt_tenant') AS jwt_tenant_exists"
                    )
                )
                row = res.fetchone()
                ok = bool(row.jwt_tenant_exists) if row else False
                return {"healthy": ok, "jwt_tenant_function": ok}
        except Exception as e:
            logger.error("RLS functions health check failed", error=str(e))
            return {"healthy": False, "error": str(e)}
