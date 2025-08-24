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


def test_full_flow_bootstrap_createuser_login_me_change_password(client: TestClient):
    # Arrange
    tenant = f"E2E-{uuid.uuid4()}"
    owner_email = f"owner-{uuid.uuid4()}@example.test"
    owner_pw = "P@ssw0rd!!"

    data = _bootstrap(client, tenant, owner_email, owner_pw)

    # Login as owner (SUPER_ADMIN)
    owner_token = _login(client, tenant, owner_email, owner_pw)

    # Admin creates a STAFF user
    staff_email = f"staff-{uuid.uuid4()}@example.test"
    staff_pw = "Str0ng-Pass!!"
    r = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": staff_email, "password": staff_pw, "role": "STAFF"},
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["email"].lower() == staff_email.lower()
    assert created["role"] == "STAFF"

    # Login as STAFF user
    staff_token = _login(client, tenant, staff_email, staff_pw)

    # /me
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {staff_token}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"].lower() == staff_email.lower()
    assert me["role"] == "STAFF"

    # Change password
    new_pw = "N3w-P@ssw0rd!!"
    r = client.post(
        "/api/v1/auth/password/change",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"old_password": staff_pw, "new_password": new_pw},
    )
    assert r.status_code == 200, r.text

    # Old password should now fail
    r = client.post("/api/v1/auth/login", json={"tenant_name": tenant, "email": staff_email, "password": staff_pw})
    assert r.status_code == 401
    assert r.json()["code"] in {"invalid_credentials", "unauthorized"}

    # New password works
    new_token = _login(client, tenant, staff_email, new_pw)
    assert isinstance(new_token, str) and len(new_token) > 10
