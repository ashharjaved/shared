from __future__ import annotations
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.domain.value_objects import TenantType
from src.identity.infrastructure.models import Tenant

    
class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_name(self, name: str) -> Optional[Tenant]:
        stmt = select(Tenant).where(Tenant.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_platform_owner(self, name: str, billing_email: Optional[str]) -> Tenant:
        ten = Tenant(name=name, tenant_type=TenantType.PLATFORM_OWNER, billing_email=billing_email, is_active=True)
        self.session.add(ten)
        await self.session.flush()
        return ten