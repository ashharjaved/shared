# tests/integration/test_login_negative.py
async def test_login_invalid_password(app_client):
    resp = await app_client.post("/api/v1/auth/token",
                                 json={"email": "x@x.com", "password": "bad"})
    assert resp.status_code == 401
