import os
from fastapi.testclient import TestClient
from uuid import uuid4
from jose import jwt
from src.main import app

client = TestClient(app)
ALG = os.getenv("JWT_ALG","HS256"); SECRET = os.getenv("JWT_SECRET","dev-insecure-secret-change-me")

def test_refresh_token_flow():
    t = client.post("/identity/tenants", json={"name":f"REF-{uuid4()}","tenant_type":"CLIENT"}).json()["id"]
    admin = jwt.encode({"sub": str(uuid4()), "tenant_id": t, "role": "TENANT_ADMIN", "email":"a@t.test"}, SECRET, algorithm=ALG)

    ur = client.post("/identity/users",
                     headers={"Authorization": f"Bearer {admin}"},
                     json={"email":"r@t.test","password":"P@ss12345","role":"STAFF","is_verified":True})
    assert ur.status_code in (200,201)

    lr = client.post("/identity/login",
                     headers={"Authorization": f"Bearer {admin}"},
                     json={"email":"r@t.test","password":"P@ss12345"})
    assert lr.status_code == 200
    refresh = lr.json()["refresh_token"]

    rr = client.post("/identity/token/refresh", json={"refresh_token": refresh})
    assert rr.status_code == 200
    assert "access_token" in rr.json()
