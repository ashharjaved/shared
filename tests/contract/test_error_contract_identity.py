from fastapi.testclient import TestClient


def test_error_contract_unauthorized(client: TestClient):
    r = client.get("/api/v1/auth/me")  # no token
    assert r.status_code == 401
    data = r.json()
    assert set(data.keys()) == {"code", "message", "details"}
    assert data["code"] in {"unauthorized", "invalid_credentials"}
