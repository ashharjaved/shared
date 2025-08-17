from __future__ import annotations
from passlib.context import CryptContext
from ..infrastructure.repositories import TenantRepository, UserRepository
from .commands import CreateTenant, CreateUser, AssignRole, UpdateTenant, UpdateTenantStatus
from .queries import GetTenant, GetUser

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Tenants
async def handle_create_tenant(cmd: CreateTenant, repo: TenantRepository):
    return await repo.create(
        name=cmd.name,
        tenant_type=cmd.tenant_type,
        subscription_plan=cmd.subscription_plan,
        billing_email=cmd.billing_email,
    )

async def handle_get_tenant(q: GetTenant, repo: TenantRepository):
    return await repo.by_id(q.tenant_id)

async def handle_update_tenant(cmd: UpdateTenant, repo: TenantRepository):
    return await repo.update(
        cmd.tenant_id,
        name=cmd.name,
        tenant_type=cmd.tenant_type,
        subscription_plan=cmd.subscription_plan,
        billing_email=cmd.billing_email,
    )

async def handle_update_tenant_status(cmd: UpdateTenantStatus, repo: TenantRepository):
    return await repo.update_status(
        cmd.tenant_id,
        is_active=cmd.is_active,
        subscription_status=cmd.subscription_status,
    )

# Users
async def handle_create_user(cmd: CreateUser, repo: UserRepository):
    pw_hash = pwd_ctx.hash(cmd.password)
    return await repo.create(cmd.tenant_id, email=cmd.email, password_hash=pw_hash, roles=cmd.roles)

async def handle_get_user(q: GetUser, repo: UserRepository):
    return await repo.by_id(q.tenant_id, q.user_id)

async def handle_assign_role(cmd: AssignRole, repo: UserRepository):
    return await repo.assign_role(cmd.tenant_id, cmd.user_id, cmd.role)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)
