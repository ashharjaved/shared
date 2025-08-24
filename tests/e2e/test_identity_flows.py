import os
import uuid
import pytest

from fastapi.testclient import TestClient

BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "change-me-bootstrap")


@pytest.mark.order(1)
def test_bootstrap_and_login_flow(client: TestClient):
    tenant_name = f"Owner-{uuid.uuid4()}"
    owner_email = f"owner-{uuid.uuid4()}@example.test"
    owner_password = "P@ssw0rd!!"

    # Bootstrap
    r = client.post(
        "/api/v1/admin/bootstrap",
        headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
        json={"tenant_name": tenant_name, "owner_email": owner_email, "owner_password": owner_password},
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert data["tenant_name"] == tenant_name
    assert "tenant_id" in data

    # Login
    r = client.post("/api/v1/auth/login", json={"tenant_name": tenant_name, "email": owner_email, "password": owner_password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    # Me
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"].lower() == owner_email.lower()
    assert me["role"] == "SUPER_ADMIN"
