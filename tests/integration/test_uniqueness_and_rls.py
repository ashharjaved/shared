import os
import uuid
import pytest
from fastapi.testclient import TestClient

BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "change-me-bootstrap")

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set; these tests require a live Postgres with the frozen SQL pack"
)


def _bootstrap(client: TestClient, tenant_name: str, owner_email: str, owner_password: str):
    r = client.post(
        "/api/v1/admin/bootstrap",
        headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
        json={
            "tenant_name": tenant_name,
            "owner_email": owner_email,
            "owner_password": owner_password
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _login(client: TestClient, tenant_name: str, email: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"tenant_name": tenant_name, "email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_per_tenant_uniqueness_and_cross_tenant_isolation(client: TestClient):
    # Setup two tenants via bootstrap
    t1 = f"T1-{uuid.uuid4()}"
    u1 = f"u1-{uuid.uuid4()}@example.test"
    pw = "P@ssw0rd!!"
    _bootstrap(client, t1, u1, pw)
    token_t1 = _login(client, t1, u1, pw)

    t2 = f"T2-{uuid.uuid4()}"
    u2 = f"u2-{uuid.uuid4()}@example.test"
    _bootstrap(client, t2, u2, pw)
    token_t2 = _login(client, t2, u2, pw)

    # 1) Same email inside same tenant -> 409
    dup = f"dup-{uuid.uuid4()}@example.test"
    r = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token_t1}"},
        json={"email": dup, "password": "Xx@123456", "role": "STAFF"},
    )
    assert r.status_code == 201, r.text

    r = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token_t1}"},
        json={"email": dup, "password": "Xx@123456", "role": "STAFF"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "conflict"

    # 2) Same email across different tenants -> allowed
    r = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token_t2}"},
        json={"email": dup, "password": "Xx@123456", "role": "STAFF"},
    )
    assert r.status_code == 201, r.text

    # 3) RLS isolation: user created in T1 cannot be used to login to T2
    r = client.post("/api/v1/auth/login", json={"tenant_name": t2, "email": dup, "password": "Xx@123456"})
    assert r.status_code in (401, 404), r.text
    # If tenant exists, user shouldn’t be visible due to RLS; service returns 401 invalid_credentials
