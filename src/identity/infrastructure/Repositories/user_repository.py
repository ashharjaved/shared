from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.domain.value_objects import Role
from src.identity.infrastructure.models import User
from src.shared.exceptions import ConflictError, NotFoundError

logger = logging.getLogger("app.repo")


# async def assert_rls_set(session: AsyncSession) -> None:
#     # Validate GUC set to avoid cross-tenant leakage
#     res = await session.execute(select(1).where())
#     # A cheap query above ensures connection checked out; now read setting
#     val = (await session.execute("SELECT current_setting('app.jwt_tenant', true)")).scalar()
#     if not val:
#         logger.error("RLS GUC app.jwt_tenant not set prior to tenant-scoped access")
#         raise RuntimeError("RLS GUC not set")

async def assert_rls_set(session: AsyncSession) -> None:
    # Validate connection and RLS setting
    await session.execute(text("SELECT 1"))  # Simple connection check
    val = await session.scalar(text("SELECT current_setting('app.jwt_tenant', true)"))
    if not val:
        logger.error("RLS GUC app.jwt_tenant not set prior to tenant-scoped access")
        raise RuntimeError("RLS GUC not set")

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        await assert_rls_set(self.session)
        stmt = select(User).where(User.email == email)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        await assert_rls_set(self.session)
        stmt = select(User).where(User.id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_user(self, *, tenant_id: UUID, email: str, password_hash: str, role: Role) -> User:
        await assert_rls_set(self.session)
        user = User(tenant_id=tenant_id, email=email, password_hash=password_hash, role=role)
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as e:
            raise ConflictError("Email already exists for this tenant") from e
        return user

    async def set_failed_attempts(self, user_id: UUID, attempts: int) -> None:
        await assert_rls_set(self.session)
        await self.session.execute(update(User).where(User.id == user_id).values(failed_login_attempts=attempts))

    async def set_last_login(self, user_id: UUID) -> None:
        await assert_rls_set(self.session)
        await self.session.execute(update(User).where(User.id == user_id).values(last_login=func.now()))

    async def change_password(self, user_id: UUID, new_hash: str) -> None:
        await assert_rls_set(self.session)
        await self.session.execute(
            update(User).where(User.id == user_id).values(password_hash=new_hash, password_changed_at=func.now())
        )

    async def ensure_user(self, *, tenant_id: UUID, email: str, password_hash: str, role: Role) -> User:
        await assert_rls_set(self.session)
        existing = await self.get_by_email(email=email)
        if existing is not None:
            # Normalize to string; ORM column is a DB enum mapped as text
            new_role = getattr(role, "value", str(role))
            curr_role = getattr(existing, "role", None)
            if curr_role != new_role:
                setattr(existing, "role", new_role)  # avoid Column[str] assignment typing error
                await self.session.flush()
            return existing
        return await self.create_user(
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            role=getattr(role, "value", role),
        )