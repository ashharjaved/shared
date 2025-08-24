import os
import uuid
import pytest
from fastapi.testclient import TestClient

BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "change-me-bootstrap")


@pytest.mark.order(2)
def test_cross_tenant_access_forbidden(client: TestClient):
    # Ensure DB exists for this test; we rely on bootstrap endpoint to create tenants/users
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL not set")

    def bootstrap(tenant_name, email):
        r = client.post(
            "/api/v1/admin/bootstrap",
            headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
            json={"tenant_name": tenant_name, "owner_email": email, "owner_password": "P@ssw0rd!!"},
        )
        assert r.status_code in (200, 201)
        return r.json()

    t1 = f"T1-{uuid.uuid4()}"
    u1 = f"u1-{uuid.uuid4()}@example.test"
    t2 = f"T2-{uuid.uuid4()}"
    u2 = f"u2-{uuid.uuid4()}@example.test"

    bootstrap(t1, u1)
    bootstrap(t2, u2)

    # Login as T1 owner
    r = client.post("/api/v1/auth/login", json={"tenant_name": t1, "email": u1, "password": "P@ssw0rd!!"})
    token_t1 = r.json()["access_token"]

    # Attempt to create user in T2 while authenticated as T1 (should still be scoped to T1 via RLS)
    r = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token_t1}"},
        json={"email": f"hacker-{uuid.uuid4()}@example.test", "password": "P@ssw0rd!!", "role": "TENANT_ADMIN"},
    )
    # It will succeed but only in T1; we verify by trying to login to T2 using that email should fail
    assert r.status_code == 201

    r = client.post("/api/v1/auth/login", json={"tenant_name": t2, "email": r.json()['email'], "password": "P@ssw0rd!!"})
    # Wrong tenant; should be invalid credentials
    assert r.status_code in (401, 404)
