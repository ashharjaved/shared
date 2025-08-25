# from __future__ import annotations

# import logging
# from contextvars import ContextVar
# from typing import AsyncIterator, Optional

# from sqlalchemy.ext.asyncio import (
#     AsyncSession,
#     async_sessionmaker,
#     create_async_engine,
# )
# from sqlalchemy import text

# from src.config import get_settings

# logger = logging.getLogger("app.db")

# _engine = create_async_engine(str(get_settings().DATABASE_URL), echo=False, future=True, pool_pre_ping=True)
# SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


# async def set_rls_gucs(session, *, tenant_id: str, user_id: Optional[str] = None, role: Optional[str] = None) -> None:
#     """
#     Set per-request RLS context. Uses set_config(..., true) to scope values to the current transaction.
#     Must be called *before* any tenant-scoped query.
#     """
#     # tenant (REQUIRED)
#     await session.execute(
#         text("SELECT set_config('app.jwt_tenant', :tenant_id, true)"),
#         {"tenant_id": tenant_id},
#     )
#     # user (OPTIONAL)
#     if user_id:
#         await session.execute(
#             text("SELECT set_config('app.jwt_user', :user_id, true)"),
#             {"user_id": user_id},
#         )
#     # role (OPTIONAL)
#     if role:
#         await session.execute(
#             text("SELECT set_config('app.jwt_role', :role, true)"),
#             {"role": role},
#         )


# async def get_db() -> AsyncIterator[AsyncSession]:
#     """
#     Yields a transaction-scoped AsyncSession and sets the RLS GUCs
#     from the per-request ContextVars (tenant_ctx, user_ctx, roles_ctx).
#     Must be used by all routes that touch the DB.
#     """
#     async with SessionLocal() as session:
#         # open a transaction so set_config(..., true) is scoped correctly
#         async with session.begin():
#             await set_rls_gucs(
#                 session,
#                 tenant_id=tenant_ctx.get() or "",   # pass empty if not set; safe for platform-scoped tables
#                 user_id=user_ctx.get() or None,
#                 role=roles_ctx.get() or None,
#             )
#         # after GUCs are set, yield the session for repositories
#         yield session
# src/shared/database.py
"""
Async SQLAlchemy engine + session factory for PostgreSQL.

Exports:
- engine: AsyncEngine
- SessionLocal: async_sessionmaker[AsyncSession]
- get_sessionmaker(request) -> async_sessionmaker[AsyncSession]
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from contextvars import ContextVar
try:
    from src.config import get_settings  # type: ignore
except Exception:  # pragma: no cover
    import os

    class _Fallback:
        DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:123456@localhost:5432/centralize_api_test")
                                                    #"postgresql+asyncpg://postgresql:postgres@localhost:5432/centralize_api"
        DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"
        DB_NULL_POOL: bool = os.getenv("DB_NULL_POOL", "false").lower() == "true"

    settings = _Fallback()  # type: ignore

# Get settings instance
settings = get_settings()

tenant_ctx: ContextVar[str | None] = ContextVar("tenant_ctx", default=None)
user_ctx: ContextVar[str | None] = ContextVar("user_ctx", default=None)
roles_ctx: ContextVar[str | None] = ContextVar("roles_ctx", default=None)

def _create_engine() -> AsyncEngine:
    poolclass = NullPool if getattr(settings, "DB_NULL_POOL", False) else None
    return create_async_engine(
        settings.DATABASE_URL,
        echo=getattr(settings, "DB_ECHO", False),
        pool_pre_ping=True,
        poolclass=poolclass,  # None -> default pool
        isolation_level="READ COMMITTED",
    )


engine: AsyncEngine = _create_engine()

# Global sessionmaker used across the app (request-scoped sessions are opened in dependencies)
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
async def set_rls_gucs(session: AsyncSession, tenant_id: str | None, user_id: str | None, roles: str | None) -> None:
    # SET LOCAL requires a transaction scope; caller must be inside session.begin()
    if tenant_id:
        #await session.execute(text("SET LOCAL app.jwt_tenant = :t"), {"t": tenant_id})
        await session.execute(
        text("SELECT set_config('app.jwt_tenant', :v, true)"),
        {"v": tenant_id},)
    if user_id:
        await session.execute(text("SELECT set_config('app.user_id',:v, true)"), {"v":user_id},)
    if roles:
        await session.execute(text("SELECT set_config('app.roles',:v, true)"), {"v":roles},)

# Optional DI helper — allows tests/ASGI lifespan to install a different sessionmaker on app.state
def get_sessionmaker(request) -> async_sessionmaker[AsyncSession]:  # FastAPI Request injected by Depends
    state_sm = getattr(getattr(request, "app", None), "state", None)
    if state_sm and getattr(state_sm, "sessionmaker", None):
        return state_sm.sessionmaker  # type: ignore[return-value]
    return SessionLocal
