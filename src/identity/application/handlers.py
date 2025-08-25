from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.application.commands import BootstrapPlatform, CreateUser
from src.identity.domain.services import AuthenticationService
from src.identity.domain.value_objects import Role
from src.identity.infrastructure.Repositories import TenantRepository, UserRepository
from src.shared.database import set_rls_gucs
from src.shared.security import get_password_hasher, get_token_provider


class IdentityHandlers:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenants = TenantRepository(session)
        self.users = UserRepository(session)
        # Wire abstractions
        self.hasher = get_password_hasher()
        self.tokens = get_token_provider()
        self.auth = AuthenticationService(self.users, self.tenants, self.hasher, self.tokens)

    async def bootstrap(self, cmd: BootstrapPlatform) -> dict:
        """Create platform owner tenant and SUPER_ADMIN user. Idempotent."""
        tenant = await self.tenants.get_by_name(cmd.tenant_name)
        if not tenant:
            tenant = await self.tenants.create_platform_owner(cmd.tenant_name, cmd.billing_email)

        # Set RLS to new tenant before touching users
        await set_rls_gucs(self.session, tenant_id= str(tenant.id),user_id= None, role="SUPER_ADMIN")

        owner = await self.users.ensure_user(
            tenant_id=tenant.id,
            email=str(cmd.owner_email),
            password_hash=self.hasher.hash(cmd.owner_password),
            role=Role.SUPER_ADMIN,
        )
        return {
            "tenant_id": str(tenant.id),
            "owner_user_id": str(owner.id),
            "tenant_name": tenant.name,
        }

    async def admin_create_user(self, *, tenant_id: UUID, cmd: CreateUser) -> dict:
        user = await self.users.create_user(
            tenant_id=tenant_id,
            email=str(cmd.email),
            password_hash=self.hasher.hash(cmd.password),
            role=Role(cmd.role.value),
        )
        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "tenant_id": str(user.tenant_id),
        }
