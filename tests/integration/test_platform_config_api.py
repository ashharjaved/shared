import uuid
import pytest
from httpx import AsyncClient
from fastapi import FastAPI
from src.main import app as real_app

TENANT_ID = str(uuid.uuid4())

class FakePrincipal:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.user_id = str(uuid.uuid4())

@pytest.fixture
def app(monkeypatch) -> FastAPI:
    # Override get_principal to return a fixed tenant
    from src.shared import security
    async def fake_get_principal():
        return FakePrincipal(TENANT_ID)
    monkeypatch.setattr(security, "get_principal", fake_get_principal, raising=True)

    # Patch ConfigRepository with in-memory dict
    from src.platform.infrastructure import repositories
    store: dict[tuple[str, str], object] = {}

    class FakeRepo:
        def __init__(self, _):
            pass
        async def get(self, tenant_id: str, key: str):
            val = store.get((tenant_id, key))
            return (key, val) if val is not None else None
        async def upsert(self, tenant_id: str, key: str, value):
            store[(tenant_id, key)] = value
            return (key, value)
        async def list(self, tenant_id: str, limit: int, offset: int):
            items = [(k, v) for (t, k), v in store.items() if t == tenant_id]
            items.sort()
            return items[offset: offset + limit]

    monkeypatch.setattr(repositories, "ConfigRepository", FakeRepo, raising=True)
    return real_app

@pytest.mark.anyio
async def test_put_get_and_list_config(app: FastAPI):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # PUT (upsert)
        resp = await ac.put("/api/v1/config/support_email", json={"key": "support_email", "value": "help@example.com"})
        assert resp.status_code == 200
        assert resp.json()["value"] == "help@example.com"

        # GET by key
        resp = await ac.get("/api/v1/config/support_email")
        assert resp.status_code == 200
        assert resp.json()["value"] == "help@example.com"

        # GET list
        resp = await ac.get("/api/v1/config")
        assert resp.status_code == 200
        items = resp.json()["items"]
        keys = [i["key"] for i in items]
        assert "support_email" in keys

@pytest.mark.anyio
async def test_get_missing_returns_404(app: FastAPI):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/config/does_not_exist")
        assert resp.status_code == 404
