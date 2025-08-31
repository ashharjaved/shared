import os
from fastapi.testclient import TestClient
from src.main import app

def test_rate_limit_per_endpoint(monkeypatch):
    monkeypatch.setenv("API_RATE_LIMIT_PER_MIN", "2")  # allow only 2 per minute

    client = TestClient(app)
    # Use unauth calls to /identity/tenants (keyed as anon)
    r1 = client.post("/identity/tenants", json={"name":"rl-1","tenant_type":"CLIENT"})
    r2 = client.post("/identity/tenants", json={"name":"rl-2","tenant_type":"CLIENT"})
    r3 = client.post("/identity/tenants", json={"name":"rl-3","tenant_type":"CLIENT"})
    assert r3.status_code == 429
    body = r3.json()
    assert body["code"] == "rate_limited"
