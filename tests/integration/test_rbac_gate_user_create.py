import os
from fastapi.testclient import TestClient
from uuid import uuid4
from jose import jwt
from src.main import app

client = TestClient(app)
ALG = os.getenv("JWT_ALG","HS256"); SECRET = os.getenv("JWT_SECRET","dev-insecure-secret-change-me")

def _token(tenant_id: str, role: str):
    return jwt.encode({"sub": str(uuid4()), "tenant_id": tenant_id, "role": role, "email": f"{role.lower()}@t.test"}, SECRET, algorithm=ALG)

def test_user_create_requires_admin_roles():
    # bootstrap tenant
    t = client.post("/identity/tenants", json={"name":f"RBAC-{uuid4()}","tenant_type":"CLIENT"}).json()["id"]
    staff = _token(t, "STAFF")  # not allowed
    admin = _token(t, "TENANT_ADMIN")  # allowed

    r_forbidden = client.post("/identity/users",
        headers={"Authorization": f"Bearer {staff}"},
        json={"email":"x@t.test","password":"P@ss12345","role":"STAFF"})
    assert r_forbidden.status_code == 403
    assert r_forbidden.json()["code"] in ("forbidden","FORBIDDEN","forbidden")

    r_ok = client.post("/identity/users",
        headers={"Authorization": f"Bearer {admin}"},
        json={"email":"ok@t.test","password":"P@ss12345","role":"STAFF"})
    assert r_ok.status_code in (200,201)
