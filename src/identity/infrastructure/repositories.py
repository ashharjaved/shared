from __future__ import annotations
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from .models import Tenant, User

async def _set_tenant(session: AsyncSession, tenant_id: str | UUID | None) -> None:
    # RLS guard using app.jwt_tenant GUC; no-op for platform-scoped tables.
    if tenant_id:
        await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": str(tenant_id)},)


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, name: str, tenant_type: str, subscription_plan: str, billing_email: Optional[str]) -> Tenant:
        t = Tenant(name=name, tenant_type=tenant_type, subscription_plan=subscription_plan, billing_email=billing_email)
        self.session.add(t)
        await self.session.flush()
        return t

    async def list(self, active_only: bool = True):
        stmt = select(Tenant)
        if active_only:
            stmt = stmt.where(Tenant.is_active.is_(True))
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows

    async def by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        return (await self.session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()

    async def set_status(self, tenant_id: UUID, *, is_active: bool) -> bool:
        res = await self.session.execute(
            update(Tenant).where(Tenant.id == tenant_id).values(is_active=is_active)
        )
        return (res.rowcount or 0) > 0

    async def update(
        self,
        tenant_id: UUID,
        *,
        name: Optional[str] = None,
        tenant_type: Optional[str] = None,
        subscription_plan: Optional[str] = None,
        billing_email: Optional[str] = None,
    ) -> Optional[Tenant]:
        values = {}
        if name is not None:
            values["name"] = name
        if tenant_type is not None:
            values["tenant_type"] = tenant_type
        if subscription_plan is not None:
            values["subscription_plan"] = subscription_plan
        if billing_email is not None:
            values["billing_email"] = billing_email
        if not values:
            # nothing to update
            return await self.by_id(tenant_id)

        await self.session.execute(update(Tenant).where(Tenant.id == tenant_id).values(**values))
        await self.session.flush()
        return await self.by_id(tenant_id)

    async def update_status(
        self,
        tenant_id: UUID,
        *,
        is_active: Optional[bool] = None,
        subscription_status: Optional[str] = None,
    ) -> Optional[Tenant]:
        values = {}
        if is_active is not None:
            values["is_active"] = is_active
        if subscription_status is not None:
            values["subscription_status"] = subscription_status
        if not values:
            return await self.by_id(tenant_id)

        await self.session.execute(update(Tenant).where(Tenant.id == tenant_id).values(**values))
        await self.session.flush()
        return await self.by_id(tenant_id)

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, tenant_id: UUID, *, email: str, password_hash: str, role: str) -> User:
        await _set_tenant(self.session, tenant_id)
        u = User(tenant_id=tenant_id, email=email, password_hash=password_hash, role=role)
        print(u)
        self.session.add(u)
        await self.session.flush()
        return u

    async def by_id(self, tenant_id: UUID, user_id: UUID) -> Optional[User]:
        await _set_tenant(self.session, tenant_id)
        return (await self.session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    async def by_email(self, tenant_id: UUID, email: str) -> Optional[User]:
        await _set_tenant(self.session, tenant_id)
        return (await self.session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    async def assign_role(self, tenant_id: UUID, user_id: UUID, role: str) -> Optional[User]:
        await _set_tenant(self.session, tenant_id)
        user = await self.by_id(tenant_id, user_id)
        if not user:
            return None
        if user.role != role:
            user.role = role
            await self.session.flush()

        return user

    async def roles_of(self, tenant_id: UUID, user_id: UUID) -> List[str]:
        user = await self.by_id(tenant_id, user_id)
        return [user.role] if user else []
