import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text
from src.main import app

ALG = os.getenv("JWT_ALG","HS256")
SECRET = os.getenv("JWT_SECRET","dev-insecure-secret-change-me")
DB_URL = os.getenv("DATABASE_URL","postgresql+asyncpg://postgres:postgres@localhost:5432/whatsapp")

client = TestClient(app)

def _admin_token(tenant_id: str, role: str = "TENANT_ADMIN") -> str:
    return jwt.encode(
        {"sub": str(uuid4()), "tenant_id": tenant_id, "role": role, "email": f"{role.lower()}@t.test"},
        SECRET,
        algorithm=ALG,
    )

@pytest.mark.anyio
async def test_outbox_event_on_tenant_create():
    # 1) Create a tenant
    name = f"OB-TEN-{uuid4()}"
    tr = client.post("/identity/tenants", json={"name": name, "tenant_type": "CLIENT"})
    assert tr.status_code in (200, 201), tr.text
    tenant_id = tr.json()["id"]

    # 2) Verify outbox row for this tenant
    engine: AsyncEngine = create_async_engine(DB_URL, future=True)
    async with engine.connect() as conn:
        # For tenants we recorded events with tenant_id = NEW.id (see SQL patch)
        res = await conn.execute(
            text("""
                SELECT 1
                FROM outbox_events
                WHERE tenant_id = :tid
                  AND aggregate_type = 'Tenant'
                  AND aggregate_id = :tid
                  AND event_type = 'TenantChanged'
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"tid": tenant_id},
        )
        row = res.fetchone()
        assert row is not None, "No outbox event found for TenantChanged"
    await engine.dispose()

@pytest.mark.anyio
async def test_outbox_event_on_user_create():
    # 1) Create a tenant
    tname = f"OB-USE-{uuid4()}"
    tr = client.post("/identity/tenants", json={"name": tname, "tenant_type": "CLIENT"})
    assert tr.status_code in (200, 201), tr.text
    tenant_id = tr.json()["id"]

    # 2) Create a user under that tenant (TENANT_ADMIN permission)
    token = _admin_token(tenant_id, "TENANT_ADMIN")
    ur = client.post(
        "/identity/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "outbox_user@test.io", "password": "P@ssw0rd123", "role": "STAFF", "is_verified": True},
    )
    assert ur.status_code in (200, 201), ur.text
    user_id = ur.json()["id"]

    # 3) Verify outbox row for this user
    engine: AsyncEngine = create_async_engine(DB_URL, future=True)
    async with engine.connect() as conn:
        res = await conn.execute(
            text("""
                SELECT 1
                FROM outbox_events
                WHERE tenant_id = :tid
                  AND aggregate_type = 'User'
                  AND aggregate_id = :uid
                  AND event_type = 'UserChanged'
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"tid": tenant_id, "uid": user_id},
        )
        row = res.fetchone()
        assert row is not None, "No outbox event found for UserChanged"
    await engine.dispose()
