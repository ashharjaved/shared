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


def _login(client: TestClient, tenant_name: str, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"tenant_name": tenant_name, "email": email, "password": password})


def test_lockout_after_max_failures_and_429(client: TestClient):
    tenant = f"LOCK-{uuid.uuid4()}"
    email = f"user-{uuid.uuid4()}@example.test"
    pw = "P@ssw0rd!!"
    _bootstrap(client, tenant, email, pw)

    # 5 failed attempts -> 401; 6th -> 429
    for i in range(5):
        r = _login(client, tenant, email, "wrong-" + pw)
        assert r.status_code == 401, r.text
        assert r.json()["code"] in {"invalid_credentials", "unauthorized"}

    r = _login(client, tenant, email, "wrong-" + pw)
    assert r.status_code == 429, r.text
    assert r.json()["code"] == "rate_limited"

    # Correct password *during* cooldown should still be blocked with 429
    r = _login(client, tenant, email, pw)
    assert r.status_code == 429, r.text


def test_failed_attempts_reset_on_success_before_threshold(client: TestClient):
    tenant = f"RESET-{uuid.uuid4()}"
    email = f"user-{uuid.uuid4()}@example.test"
    pw = "P@ssw0rd!!"
    _bootstrap(client, tenant, email, pw)

    # 4 failed (below threshold)
    for i in range(4):
        r = _login(client, tenant, email, "wrong-" + pw)
        assert r.status_code == 401, r.text

    # Successful login should be allowed and reset counter
    r = _login(client, tenant, email, pw)
    assert r.status_code == 200, r.text

    # Another wrong attempt should be 401 (not 429), proving reset
    r = _login(client, tenant, email, "wrong-" + pw)
    assert r.status_code == 401, r.text
