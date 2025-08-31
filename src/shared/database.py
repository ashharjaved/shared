from __future__ import annotations
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""
    pass

# NOTE: DB is the source of truth (see REDIS policy). Pool pre-ping enabled.
# Add URL validation
DATABASE_URL = os.getenv("DATABASE_URL") or ""

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

_engine = create_async_engine(DATABASE_URL, future=True, pool_pre_ping=True)
_Session = async_sessionmaker(bind=_engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncIterator[AsyncSession]:
    async with _Session() as session:
        yield session

async def set_rls_guc(
    session: AsyncSession,
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    roles: str | None = None,
) -> None:
    """
    Conforms to RLS_GUC_CONTRACT.md:
      - app.jwt_tenant
      - app.user_id
      - app.roles
    """
    # Use a SAVEPOINT so we don't interfere with caller tx semantics
    async with session.begin_nested():
        if tenant_id is not None:
            await session.execute(text("SET LOCAL app.jwt_tenant = :t"), {"t": tenant_id})
        if user_id is not None:
            await session.execute(text("SET LOCAL app.user_id = :u"), {"u": user_id})
        if roles is not None:
            await session.execute(text("SET LOCAL app.roles = :r"), {"r": roles})
