from uuid import uuid4

import pytest
from sqlalchemy import text


async def test_rls_guard(session):
    tenant_id = uuid4()
    await session.execute(text("SET LOCAL app.jwt_tenant = :t"), {"t": str(tenant_id)})
    with pytest.raises(Exception):
        await session.execute(text("INSERT INTO users (tenant_id, email, password_hash, role) VALUES (:tid, 'x@test', 'hash', 'STAFF')"), {"tid": str(uuid4())})
