# Identity Infrastructure Layer

## Overview

This layer implements:
- **ORM Models**: SQLAlchemy 2.0 models for all 9 identity tables
- **Repositories**: Domain entity persistence with RLS enforcement
- **Unit of Work**: Transaction coordination with RLS, Outbox, and Idempotency
- **Services**: Audit logging and idempotency management
- **Adapters**: JWT and password management

---

## RLS Enforcement

**CRITICAL**: All tenant-scoped operations MUST set RLS context.

### Usage
```python
from modules.identity.infrastructure import IdentityUnitOfWork

async with uow:
    # Set tenant context (REQUIRED for RLS)
    uow.set_tenant_context(
        organization_id=org_id,
        user_id=user_id,
        roles=["TenantAdmin"],
    )
    
    # Now queries are scoped to this organization
    user = await uow.users.get_by_id(user_id)
    await uow.commit()