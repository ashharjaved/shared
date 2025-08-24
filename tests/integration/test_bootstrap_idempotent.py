import os
import uuid
import pytest
from fastapi.testclient import TestClient

BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "change-me-bootstrap")

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set; these tests require a live Postgres with the frozen SQL pack"
)


def test_bootstrap_idempotent(client: TestClient):
    tenant = f"BOOT-{uuid.uuid4()}"
    owner = f"owner-{uuid.uuid4()}@example.test"
    pw = "P@ssw0rd!!"

    for _ in range(2):
        r = client.post(
            "/api/v1/admin/bootstrap",
            headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
            json={"tenant_name": tenant, "owner_email": owner, "owner_password": pw},
        )
        assert r.status_code in (200, 201), r.text
        data = r.json()
        assert data["tenant_name"] == tenant
        assert "tenant_id" in data and "owner_user_id" in data
